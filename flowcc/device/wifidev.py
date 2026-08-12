"""WiFi 风扇设备：ESP32 固件开启 TCP 服务（默认端口 3333），
软件作为 TCP 客户端，沿用同一套 ASCII 行协议。
"""
from __future__ import annotations

import socket

from .base import DeviceError, LineProtocolDevice

DEFAULT_TCP_PORT = 3333


class WifiFanDevice(LineProtocolDevice):
    """通过局域网 TCP 与 ESP32 固件通信的风扇设备。"""

    def __init__(self, host: str, port: int = DEFAULT_TCP_PORT,
                 timeout: float = 2.0) -> None:
        super().__init__()
        if not host:
            raise DeviceError("未指定设备地址")
        self._host = host
        self._port = int(port)
        self._timeout = timeout
        self._sock: socket.socket | None = None

    # -- 字节管道原语 -------------------------------------------------------

    def _open_pipe(self) -> None:
        try:
            self._sock = socket.create_connection(
                (self._host, self._port), timeout=self._timeout)
            self._sock.settimeout(self._timeout)
        except OSError as exc:
            self._sock = None
            raise DeviceError(
                f"无法连接 {self._host}:{self._port}：{exc}") from exc

    def _close_pipe(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _write_bytes(self, data: bytes) -> None:
        self._sock.sendall(data)

    def _read_chunk(self, timeout: float) -> bytes:
        self._sock.settimeout(max(0.02, timeout))
        try:
            return self._sock.recv(256)
        except socket.timeout:
            return b""
        except OSError as exc:
            raise DeviceError(f"读取失败: {exc}") from exc

    # -- 展示 ---------------------------------------------------------------

    @property
    def label(self) -> str:
        return f"WiFi {self._host}:{self._port}"
