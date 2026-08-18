"""真实串口风扇设备（USB 转串口 + MCU 固件）。

传输层只负责字节管道；命令事务与帧解析在 LineProtocolDevice 中。
"""
from __future__ import annotations

from ..protocol import DEFAULT_BAUD
from .base import DeviceError, LineProtocolDevice


class SerialFanDevice(LineProtocolDevice):
    """通过串口（USB）与 MCU 固件通信的风扇设备。"""

    def __init__(self, port: str, baud: int = DEFAULT_BAUD,
                 serial_impl=None) -> None:
        """serial_impl 用于测试注入（需兼容 pyserial.Serial 的构造参数）。"""
        super().__init__()
        if not port:
            raise DeviceError("未指定串口")
        self._port = port
        self._baud = int(baud)
        self._serial_impl = serial_impl
        self._ser = None

    # -- 字节管道原语 -------------------------------------------------------

    def _open_pipe(self) -> None:
        impl = self._serial_impl
        if impl is None:
            try:
                import serial as pyserial  # 延迟导入：未装 pyserial 不影响其它模式
            except ImportError as exc:
                raise DeviceError(
                    "缺少 pyserial，请先执行: pip install pyserial") from exc
            impl = pyserial.Serial
        try:
            self._ser = impl(port=self._port, baudrate=self._baud,
                             timeout=0.2, write_timeout=1.0)
        except Exception as exc:  # serial.SerialException / OSError
            self._ser = None
            raise DeviceError(f"无法打开 {self._port}: {exc}") from exc

    def _close_pipe(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def _write_bytes(self, data: bytes) -> None:
        self._ser.write(data)
        self._ser.flush()

    def _read_chunk(self, timeout: float) -> bytes:
        self._ser.timeout = max(0.02, timeout)
        return self._ser.read(64)

    def _discard_input(self) -> None:
        try:
            self._ser.reset_input_buffer()
        except Exception:
            pass
        self._buffer = b""

    # -- 展示 ---------------------------------------------------------------

    @property
    def label(self) -> str:
        return f"{self._port} @ {self._baud}"
