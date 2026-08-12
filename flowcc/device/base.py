"""风扇设备抽象基类。

GUI 与控制器永远只面对 FanDevice 接口，因此「模拟设备」与
「真实串口设备」可以自由替换——这正是硬件未到位时软件先行的关键。
"""
from __future__ import annotations

import abc
from typing import Optional

from ..protocol import FanState


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
    def query_state(self) -> FanState:
        """查询当前状态（同时充当心跳探活）。"""
