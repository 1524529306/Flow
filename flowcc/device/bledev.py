"""蓝牙 BLE 风扇设备：ESP32 固件提供 Nordic UART Service（NUS），
软件用 bleak 作为 GATT 客户端，RX 写命令、TX 收上报，沿用同一套行协议。

bleak 为可选依赖：仅在选择蓝牙模式时才导入。
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import List, Optional, Tuple

from .base import DeviceError, LineProtocolDevice

logger = logging.getLogger(__name__)

# Nordic UART Service UUID（固件端一致）
NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_CHAR = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # 主机写
NUS_TX_CHAR = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # 设备通知

DEVICE_NAME_PREFIX = "FlowCC"


def scan_ble_devices(timeout: float = 4.0) -> List[Tuple[str, str]]:
    """扫描广播 FlowCC 名称的 BLE 设备，返回 [(address, name), ...]。"""
    try:
        from bleak import BleakScanner
    except ImportError as exc:
        raise DeviceError("缺少 bleak，请先执行: pip install bleak") from exc

    async def _scan():
        found = await BleakScanner.discover(timeout=timeout)
        return [(d.address, d.name or "") for d in found
                if d.name and d.name.startswith(DEVICE_NAME_PREFIX)]

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_scan())
    except Exception as exc:
        raise DeviceError(f"蓝牙扫描失败: {exc}") from exc
    finally:
        loop.close()


class BleFanDevice(LineProtocolDevice):
    """通过 BLE NUS 与 ESP32 固件通信的风扇设备。"""

    def __init__(self, address: str) -> None:
        super().__init__()
        if not address:
            raise DeviceError("未指定蓝牙地址")
        self._address = address
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._client = None
        self._rx: "queue.Queue[bytes]" = queue.Queue()

    # -- 后台事件循环 -------------------------------------------------------

    def _start_loop(self) -> None:
        self._loop = asyncio.new_event_loop()

        def _run() -> None:
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, name="BleLoop", daemon=True)
        self._thread.start()

    def _run(self, coro, timeout: float = 10.0):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except Exception as exc:
            raise DeviceError(f"蓝牙操作失败: {exc}") from exc

    async def _on_notify(self, _sender, data: bytearray) -> None:
        self._rx.put(bytes(data))

    # -- 字节管道原语 -------------------------------------------------------

    def _open_pipe(self) -> None:
        try:
            from bleak import BleakClient
        except ImportError as exc:
            raise DeviceError("缺少 bleak，请先执行: pip install bleak") from exc

        self._start_loop()

        async def _go() -> None:
            self._client = BleakClient(self._address, timeout=10.0)
            await self._client.connect()
            await self._client.start_notify(NUS_TX_CHAR, self._on_notify)

        try:
            self._run(_go())
        except DeviceError:
            self._stop_loop()
            raise

    def _close_pipe(self) -> None:
        if self._client is not None and self._loop is not None:
            try:
                self._run(self._client.disconnect(), timeout=3.0)
            except DeviceError:
                pass
            self._client = None
        self._stop_loop()

    def _stop_loop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=2.0)
            self._loop = None
            self._thread = None

    def _write_bytes(self, data: bytes) -> None:
        self._run(self._client.write_gatt_char(
            NUS_RX_CHAR, data, response=False))

    def _read_chunk(self, timeout: float) -> bytes:
        try:
            return self._rx.get(timeout=max(0.02, timeout))
        except queue.Empty:
            return b""

    # -- 展示 ---------------------------------------------------------------

    @property
    def label(self) -> str:
        return f"BLE …{self._address[-8:]}"
