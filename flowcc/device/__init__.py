"""设备抽象层：上层只关心风扇语义，不关心传输方式。"""

from .base import DeviceError, FanDevice, LineProtocolDevice
from .bledev import BleFanDevice, scan_ble_devices
from .mock import MockFanDevice
from .serialdev import SerialFanDevice
from .wifidev import WifiFanDevice, DEFAULT_TCP_PORT

__all__ = [
    "DeviceError", "FanDevice", "LineProtocolDevice",
    "MockFanDevice", "SerialFanDevice", "WifiFanDevice",
    "BleFanDevice", "scan_ble_devices", "DEFAULT_TCP_PORT",
]
