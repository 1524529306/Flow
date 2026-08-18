"""模拟风扇设备。

在没有实体硬件时完整模拟一台风扇的行为，保证软件可以独立开发、
演示和测试。行为与真实设备保持一致：同样的状态机、同样的接口。
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from ..protocol import ANGLE_MAX, ANGLE_MIN, SPEED_MAX, SPEED_MIN, FanState
from .base import DeviceError, FanDevice


class MockFanDevice(FanDevice):
    """内存中实现的假风扇，可配置通信延迟以贴近真实手感。"""

    def __init__(self, latency: float = 0.03) -> None:
        self._latency = latency
        self._lock = threading.Lock()
        self._connected = False
        self._state = FanState()

    # -- 连接管理 -----------------------------------------------------------

    def connect(self) -> None:
        with self._lock:
            time.sleep(self._latency)
            self._connected = True

    def disconnect(self) -> None:
        with self._lock:
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def label(self) -> str:
        return "模拟设备"

    @property
    def firmware(self) -> Optional[str]:
        return "MOCK-1.0"

    # -- 控制命令 -----------------------------------------------------------

    def set_power(self, on: bool) -> FanState:
        return self._mutate(power=bool(on))

    def set_speed(self, level: int) -> FanState:
        level = int(level)
        if not SPEED_MIN <= level <= SPEED_MAX:
            raise DeviceError(f"非法档位: {level}")
        return self._mutate(speed=level)

    def set_oscillation(self, on: bool) -> FanState:
        return self._mutate(oscillation=bool(on))

    def set_angle(self, degrees: int) -> FanState:
        # 与固件语义一致：手动摆头即退出自动摇头
        degrees = int(degrees)
        if not ANGLE_MIN <= degrees <= ANGLE_MAX:
            raise DeviceError(f"非法角度: {degrees}")
        return self._mutate(angle=degrees, oscillation=False)

    def query_state(self) -> FanState:
        with self._lock:
            self._ensure_connected()
            time.sleep(self._latency)
            return FanState(**self._state.__dict__)

    # -- 内部 ---------------------------------------------------------------

    def _ensure_connected(self) -> None:
        if not self._connected:
            raise DeviceError("模拟设备未连接")

    def _mutate(self, **changes) -> FanState:
        with self._lock:
            self._ensure_connected()
            time.sleep(self._latency)
            for key, value in changes.items():
                setattr(self._state, key, value)
            return FanState(**self._state.__dict__)
