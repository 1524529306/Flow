"""风扇设备抽象基类。

GUI 与控制器永远只面对 FanDevice 接口，因此「模拟设备」与
「真实串口设备」可以自由替换——这正是硬件未到位时软件先行的关键。

LineProtocolDevice 进一步把「ASCII 行协议事务」沉淀为基类，
串口 / WiFi / 蓝牙三种传输只需实现字节管道原语即可接入。
"""
from __future__ import annotations

import abc
import threading
import time
from typing import List, Optional

from ..protocol import (
    CMD_ANGLE,
    CMD_OSC,
    CMD_POWER,
    CMD_QUERY,
    CMD_SPEED,
    Message,
    MessageKind,
    FanState,
    encode_angle,
    encode_oscillation,
    encode_power,
    encode_query,
    encode_speed,
    parse_line,
)


class DeviceError(RuntimeError):
    """设备通信或执行失败。"""


class FanDevice(abc.ABC):
    """风扇设备统一接口。所有方法均应是线程安全的。"""

    @abc.abstractmethod
    def connect(self) -> None:
        """建立连接。失败时抛出 DeviceError。"""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """断开连接。幂等，不应抛异常。"""

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        ...

    @property
    @abc.abstractmethod
    def label(self) -> str:
        """用于界面展示的设备名，如「模拟设备」或「COM3 @ 115200」。"""

    @property
    def firmware(self) -> Optional[str]:
        """固件版本（来自 HELLO 帧），未知时返回 None。"""
        return None

    @abc.abstractmethod
    def set_power(self, on: bool) -> FanState:
        """设置电源，返回执行后的设备状态。"""

    @abc.abstractmethod
    def set_speed(self, level: int) -> FanState:
        """设置风速档位（1~3），返回执行后的设备状态。"""

    @abc.abstractmethod
    def set_oscillation(self, on: bool) -> FanState:
        """设置摇头开关，返回执行后的设备状态。"""

    @abc.abstractmethod
    def set_angle(self, degrees: int) -> FanState:
        """手动摆头到指定角度（0~180），返回执行后的设备状态。"""

    @abc.abstractmethod
    def query_state(self) -> FanState:
        """查询当前状态（同时充当心跳探活）。"""


class LineProtocolDevice(FanDevice):
    """行协议设备基类：串口 / WiFi / 蓝牙共享命令事务与帧解析。

    子类实现四个字节管道原语：
        _open_pipe / _close_pipe / _write_bytes / _read_chunk
    """

    READY_TIMEOUT = 3.0
    TX_TIMEOUT = 1.0

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = FanState()
        self._firmware_version: Optional[str] = None
        self._connected = False
        self._buffer = b""

    # -- 字节管道原语（子类实现） -------------------------------------------

    @abc.abstractmethod
    def _open_pipe(self) -> None:
        """建立字节管道。失败抛 DeviceError。"""

    @abc.abstractmethod
    def _close_pipe(self) -> None:
        """关闭字节管道。"""

    @abc.abstractmethod
    def _write_bytes(self, data: bytes) -> None:
        """写出字节。"""

    @abc.abstractmethod
    def _read_chunk(self, timeout: float) -> bytes:
        """在 timeout 内读取若干字节；无数据返回 b""。"""

    # -- 连接管理 -----------------------------------------------------------

    def connect(self) -> None:
        with self._lock:
            if self._connected:
                return
            self._open_pipe()  # 失败抛 DeviceError
            self._connected = True
            try:
                self._wait_ready()
                self.query_state()
            except DeviceError:
                self._connected = False
                self._close_pipe_quietly()
                raise

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False
            self._close_pipe_quietly()

    def _close_pipe_quietly(self) -> None:
        try:
            self._close_pipe()
        except Exception:
            pass

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def firmware(self) -> Optional[str]:
        return self._firmware_version

    def _wait_ready(self) -> None:
        """上电等待 HELLO 问候帧（最长 READY_TIMEOUT，可缺省）。"""
        deadline = time.monotonic() + self.READY_TIMEOUT
        while time.monotonic() < deadline:
            for message in self._read_messages(0.5):
                if message.kind is MessageKind.HELLO:
                    self._firmware_version = message.version
                    return

    # -- 控制命令 -----------------------------------------------------------

    def set_power(self, on: bool) -> FanState:
        return self._transact(encode_power(on), CMD_POWER)

    def set_speed(self, level: int) -> FanState:
        return self._transact(encode_speed(level), CMD_SPEED)

    def set_oscillation(self, on: bool) -> FanState:
        return self._transact(encode_oscillation(on), CMD_OSC)

    def set_angle(self, degrees: int) -> FanState:
        return self._transact(encode_angle(degrees), CMD_ANGLE)

    def query_state(self) -> FanState:
        return self._transact(encode_query(), CMD_QUERY)

    # -- 底层收发 -----------------------------------------------------------

    def _transact(self, line: str, expect_command: str) -> FanState:
        """发送一条命令并等待 OK/ERR。线程安全。"""
        with self._lock:
            if not self._connected:
                raise DeviceError("设备未连接")
            try:
                self._discard_input()
                self._write_bytes(line.encode("ascii"))
            except DeviceError:
                raise
            except Exception as exc:
                raise DeviceError(f"写入失败: {exc}") from exc

            deadline = time.monotonic() + self.TX_TIMEOUT
            ok_received = False
            while time.monotonic() < deadline:
                for message in self._read_messages(0.2):
                    if message.kind is MessageKind.STATE and message.state:
                        self._state = message.state
                        if ok_received:
                            return FanState(**self._state.__dict__)
                    elif message.kind is MessageKind.OK and \
                            message.command == expect_command:
                        ok_received = True
                    elif message.kind is MessageKind.ERR and \
                            message.command == expect_command:
                        raise DeviceError(
                            f"设备执行 {expect_command} 失败: {message.error_code}")
                if ok_received:
                    # OK 已收到但 STATE 可能稍后到达，给一个短宽限再读一次
                    for message in self._read_messages(0.3):
                        if message.kind is MessageKind.STATE and message.state:
                            self._state = message.state
                    return FanState(**self._state.__dict__)
            raise DeviceError(f"设备无应答（{expect_command}），请检查连接与固件")

    def _discard_input(self) -> None:
        """丢弃管道中的残留输入。子类可覆盖为更高效实现。"""
        try:
            while self._read_chunk(0.02):
                pass
        except Exception:
            pass
        self._buffer = b""

    def _read_messages(self, timeout: float) -> List[Message]:
        """读取并解析当前可得的全部完整行。"""
        messages: List[Message] = []
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            chunk = self._read_chunk(max(0.05, min(0.2, end - time.monotonic())))
            if not chunk:
                continue
            self._buffer += chunk
            while b"\n" in self._buffer:
                raw, self._buffer = self._buffer.split(b"\n", 1)
                text = raw.decode("ascii", errors="replace").strip()
                if text:
                    messages.append(parse_line(text))
        return messages
