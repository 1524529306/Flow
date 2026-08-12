"""真实串口风扇设备（USB 转串口 + MCU 固件）。

通信采用 protocol.py 定义的 ASCII 行协议。交互模型为「一问一答」：
每条命令发出后等待对应的 OK / ERR 帧，并顺带收集 STATE 上报。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import List, Optional

from ..protocol import (
    CMD_QUERY,
    DEFAULT_BAUD,
    Message,
    MessageKind,
    FanState,
    encode_oscillation,
    encode_ping,
    encode_power,
    encode_query,
    encode_speed,
    parse_line,
)
from .base import DeviceError, FanDevice

logger = logging.getLogger(__name__)


class SerialFanDevice(FanDevice):
    """通过串口（USB）与 MCU 固件通信的风扇设备。"""

    def __init__(self, port: str, baud: int = DEFAULT_BAUD,
                 timeout: float = 1.0) -> None:
        if not port:
            raise DeviceError("未指定串口")
        self._port = port
        self._baud = int(baud)
        self._timeout = timeout
        self._serial = None
        self._lock = threading.RLock()
        self._state = FanState()
        self._firmware: Optional[str] = None

    # -- 连接管理 -----------------------------------------------------------

    def connect(self) -> None:
        try:
            import serial  # 延迟导入：未安装 pyserial 时不影响模拟模式
        except ImportError as exc:
            raise DeviceError("缺少 pyserial，请先执行: pip install pyserial") from exc

        with self._lock:
            if self._serial is not None:
                return
            try:
                self._serial = serial.Serial(
                    port=self._port,
                    baudrate=self._baud,
                    timeout=self._timeout,
                    write_timeout=self._timeout,
                )
            except Exception as exc:  # serial.SerialException / OSError
                self._serial = None
                raise DeviceError(f"无法打开 {self._port}: {exc}") from exc

            try:
                self._wait_ready()
                self.query_state()
            except DeviceError:
                self._close_quietly()
                raise
            logger.info("已连接 %s", self.label)

    def disconnect(self) -> None:
        with self._lock:
            self._close_quietly()

    def _close_quietly(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    def _wait_ready(self) -> None:
        """上电等待：MCU 经 USB 上电会复位，等待 HELLO（最长 3 秒，可缺省）。"""
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            for message in self._read_lines(timeout=0.5):
                if message.kind is MessageKind.HELLO:
                    self._firmware = message.version
                    logger.info("设备问候: %s", message.raw)
                    return
        logger.info("未收到 HELLO 帧，继续尝试查询状态")

    @property
    def is_connected(self) -> bool:
        return self._serial is not None

    @property
    def label(self) -> str:
        return f"{self._port} @ {self._baud}"

    @property
    def firmware(self) -> Optional[str]:
        return self._firmware

    # -- 控制命令 -----------------------------------------------------------

    def set_power(self, on: bool) -> FanState:
        return self._transact(encode_power(on), "PWR")

    def set_speed(self, level: int) -> FanState:
        return self._transact(encode_speed(level), "SPD")

    def set_oscillation(self, on: bool) -> FanState:
        return self._transact(encode_oscillation(on), "OSC")

    def query_state(self) -> FanState:
        return self._transact(encode_query(), CMD_QUERY)

    # -- 底层收发 -----------------------------------------------------------

    def _transact(self, line: str, expect_command: str) -> FanState:
        """发送一条命令并等待 OK/ERR。线程安全。"""
        with self._lock:
            if self._serial is None:
                raise DeviceError("设备未连接")
            try:
                self._serial.reset_input_buffer()
                self._serial.write(line.encode("ascii"))
                self._serial.flush()
            except Exception as exc:
                raise DeviceError(f"写入 {self._port} 失败: {exc}") from exc

            deadline = time.monotonic() + self._timeout
            while time.monotonic() < deadline:
                for message in self._read_lines(timeout=0.2):
                    if message.kind is MessageKind.STATE and message.state:
                        self._state = message.state
                    elif message.kind is MessageKind.OK and \
                            message.command == expect_command:
                        return FanState(**self._state.__dict__)
                    elif message.kind is MessageKind.ERR and \
                            message.command == expect_command:
                        raise DeviceError(
                            f"设备执行 {expect_command} 失败: {message.error_code}")
            raise DeviceError(f"设备无应答（{expect_command}），请检查连接与固件")

    def _read_lines(self, timeout: float) -> List[Message]:
        """读取当前缓冲区内的完整行并解析为消息列表。"""
        assert self._serial is not None
        messages: List[Message] = []
        end = time.monotonic() + timeout
        buffer = b""
        while time.monotonic() < end:
            self._serial.timeout = max(0.05, min(0.2, end - time.monotonic()))
            try:
                chunk = self._serial.read(64)
            except Exception as exc:
                raise DeviceError(f"读取 {self._port} 失败: {exc}") from exc
            if not chunk:
                continue
            buffer += chunk
            while b"\n" in buffer:
                raw, buffer = buffer.split(b"\n", 1)
                text = raw.decode("ascii", errors="replace").strip()
                if text:
                    messages.append(parse_line(text))
        return messages
