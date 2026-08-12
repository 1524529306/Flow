"""设备抽象层：上层只关心风扇语义，不关心传输方式。"""

from .base import DeviceError, FanDevice
from .mock import MockFanDevice
from .serialdev import SerialFanDevice

__all__ = ["DeviceError", "FanDevice", "MockFanDevice", "SerialFanDevice"]
