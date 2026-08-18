"""风扇控制器：软件的大脑。

职责：
1. 维护风扇的目标状态（电源 / 档位 / 摇头 / 风模式）；
2. 在后台线程中执行定时关机、自然风/睡眠风等「场景引擎」；
3. 对串口设备做心跳轮询，自动发现掉线；
4. 向上层（GUI）提供线程安全的操作接口与状态快照。

线程模型：GUI 线程调用公开方法（入队），worker 线程统一执行设备操作，
避免任何 UI 卡顿；GUI 通过 get_snapshot() 只读地获取最新状态。
"""
from __future__ import annotations

import logging
import queue
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .device.base import DeviceError, FanDevice, LineProtocolDevice
from .device.bledev import BleFanDevice
from .device.mock import MockFanDevice
from .device.serialdev import SerialFanDevice
from .device.wifidev import DEFAULT_TCP_PORT, WifiFanDevice
from .protocol import (
    ANGLE_CENTER,
    ANGLE_MAX,
    ANGLE_MIN,
    DEFAULT_BAUD,
    SPEED_MAX,
    SPEED_MIN,
)

logger = logging.getLogger(__name__)

MODE_NORMAL = "normal"    # 恒定风
MODE_NATURAL = "natural"  # 自然风：档位随机起伏
MODE_SLEEP = "sleep"      # 睡眠风：随时间逐渐降档

MODE_LABELS = {
    MODE_NORMAL: "恒定风",
    MODE_NATURAL: "自然风",
    MODE_SLEEP: "睡眠风",
}

# 睡眠风策略：每过 SLEEP_STEP_SECONDS 秒降一档，直到最低档。
SLEEP_STEP_SECONDS = 20 * 60
# 自然风策略：每 NATURAL_INTERVAL_RANGE 秒随机换一次档。
NATURAL_INTERVAL_RANGE = (4.0, 9.0)
# 串口心跳轮询间隔与容忍失败次数。
POLL_INTERVAL = 5.0
POLL_FAIL_LIMIT = 3


def compute_sleep_speed(user_speed: int, elapsed_seconds: float) -> int:
    """睡眠风：根据已运行时长计算当前应输出的档位。纯函数，便于测试。"""
    drops = int(elapsed_seconds // SLEEP_STEP_SECONDS)
    return max(SPEED_MIN, int(user_speed) - drops)


def compute_natural_speed(user_speed: int, rng: Optional[random.Random] = None) -> int:
    """自然风：在用户档位上下各一档范围内随机取值。纯函数，便于测试。"""
    rng = rng or random.Random()
    low = max(SPEED_MIN, int(user_speed) - 1)
    high = min(SPEED_MAX, int(user_speed) + 1)
    return rng.randint(low, high)


@dataclass(frozen=True)
class Snapshot:
    """某一时刻的完整状态快照，供 GUI 渲染。"""

    power: bool
    speed: int                 # 用户设定档位
    oscillation: bool
    angle: int                 # 摆头角度 0~180（自动摇头时由设备扫动）
    mode: str
    active_speed: Optional[int]     # 实际输出档位（模式引擎可能调整）
    timer_remaining: Optional[float]
    timer_total: Optional[float]
    mute: bool                 # 风声静音（纯本地 GUI 状态）
    connected: bool
    connecting: bool
    device_label: str
    firmware: Optional[str]
    error: Optional[str]


class FanController:
    """对 GUI 暴露的线程安全门面。"""

    TICK = 0.2

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._device: Optional[FanDevice] = None

        # 目标状态
        self._power = False
        self._speed = 2
        self._oscillation = False
        self._angle = ANGLE_CENTER
        self._mode = MODE_NORMAL
        self._active_speed: Optional[int] = None
        self._mute = False           # 风声静音（纯本地，不进设备协议）

        # 定时关机
        self._timer_end: Optional[float] = None
        self._timer_total: Optional[float] = None

        # 场景引擎内部变量
        self._sleep_started: Optional[float] = None
        self._next_mode_at = 0.0

        # 心跳与诊断
        self._next_poll = 0.0
        self._poll_fails = 0
        self._error: Optional[str] = None
        self._connecting = False

        self._jobs: "queue.Queue[tuple[Callable, tuple]]" = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- 生命周期 -----------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name="FanController", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.disconnect()

    # -- 连接管理 -----------------------------------------------------------

    def connect_mock(self) -> None:
        """切换到内置模拟设备（立即成功）。"""
        device = MockFanDevice()
        device.connect()
        self._attach(device)

    def connect_serial(self, port: str, baud: int = DEFAULT_BAUD) -> None:
        """连接真实硬件。耗时操作，调用方应放在后台线程。"""
        self._set_connecting(True)
        try:
            device = SerialFanDevice(port, baud)
            device.connect()  # 失败抛 DeviceError
            self._attach(device)
        finally:
            self._set_connecting(False)

    def connect_wifi(self, host: str, port: int = DEFAULT_TCP_PORT) -> None:
        """通过 WiFi（TCP）连接设备。耗时操作，调用方应放在后台线程。"""
        self._set_connecting(True)
        try:
            device = WifiFanDevice(host, port)
            device.connect()
            self._attach(device)
        finally:
            self._set_connecting(False)

    def connect_ble(self, address: str) -> None:
        """通过蓝牙 BLE 连接设备。耗时操作，调用方应放在后台线程。"""
        self._set_connecting(True)
        try:
            device = BleFanDevice(address)
            device.connect()
            self._attach(device)
        finally:
            self._set_connecting(False)

    def disconnect(self) -> None:
        with self._lock:
            device, self._device = self._device, None
        if device is not None:
            device.disconnect()
        with self._lock:
            self._active_speed = None
            self._poll_fails = 0

    def _attach(self, device: FanDevice) -> None:
        """挂接新设备，并把当前目标状态同步下去。"""
        with self._lock:
            old, self._device = self._device, device
            self._poll_fails = 0
            self._error = None
            self._next_poll = time.monotonic() + POLL_INTERVAL
            target = (self._speed, self._angle, self._oscillation,
                      self._power, self._mode)
        if old is not None:
            old.disconnect()
        speed, angle, osc, power, mode = target
        self._push_state_to_device(speed, angle, osc, power)
        with self._lock:
            self._sleep_started = time.monotonic() if power else None
            self._active_speed = speed if power else None
            self._next_mode_at = 0.0
            logger.info("设备已挂接: %s", device.label)

    def _push_state_to_device(self, speed: int, angle: int, osc: bool,
                              power: bool) -> None:
        device = self._device
        if device is None:
            return
        try:
            device.set_speed(speed)
            device.set_angle(angle)
            device.set_oscillation(osc)
            device.set_power(power)
        except DeviceError as exc:
            with self._lock:
                self._error = str(exc)

    def _set_connecting(self, value: bool) -> None:
        with self._lock:
            self._connecting = value

    # -- GUI 操作入口（线程安全，worker 中执行） ------------------------------

    def set_power(self, on: bool) -> None:
        self._post(self._do_set_power, bool(on))

    def set_speed(self, level: int) -> None:
        self._post(self._do_set_speed, int(level))

    def set_oscillation(self, on: bool) -> None:
        self._post(self._do_set_oscillation, bool(on))

    def set_mute(self, muted: bool) -> None:
        """风声静音开关。纯本地 GUI 状态，直接写（与设备无关）。"""
        with self._lock:
            self._mute = bool(muted)

    def set_angle(self, degrees: int) -> None:
        """手动摆头（0~180）。会隐式关闭自动摇头。"""
        self._post(self._do_set_angle, int(degrees))

    def set_mode(self, mode: str) -> None:
        if mode not in MODE_LABELS:
            raise ValueError(f"未知模式: {mode}")
        self._post(self._do_set_mode, mode)

    def set_timer_minutes(self, minutes: int) -> None:
        """minutes<=0 表示取消定时。"""
        self._post(self._do_set_timer, int(minutes))

    def apply_preset(self, speed: Optional[int] = None,
                     oscillation: Optional[bool] = None,
                     mode: Optional[str] = None,
                     angle: Optional[int] = None,
                     mute: Optional[bool] = None) -> None:
        """启动时用配置预热状态（不改变电源）。"""
        with self._lock:
            if speed is not None and SPEED_MIN <= speed <= SPEED_MAX:
                self._speed = speed
            if oscillation is not None:
                self._oscillation = bool(oscillation)
            if mode in MODE_LABELS:
                self._mode = mode  # type: ignore[assignment]
            if angle is not None and ANGLE_MIN <= angle <= ANGLE_MAX:
                self._angle = angle
            if mute is not None:
                self._mute = bool(mute)

    def _post(self, fn: Callable, *args) -> None:
        self._jobs.put((fn, args))

    # -- worker 主循环 -------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.wait(self.TICK):
            try:
                while True:
                    fn, args = self._jobs.get_nowait()
                    fn(*args)
            except queue.Empty:
                pass
            except Exception:
                logger.exception("执行控制命令出错")
            try:
                self._tick_timer()
                self._tick_mode_engine()
                self._tick_poll()
            except Exception:
                logger.exception("后台任务出错")

    def _device_or_none(self) -> Optional[FanDevice]:
        with self._lock:
            return self._device

    # -- 命令执行 -----------------------------------------------------------

    def _do_set_power(self, on: bool) -> None:
        device = self._device_or_none()
        if device is None:
            return
        try:
            state = device.set_power(on)
            with self._lock:
                self._power = state.power
                self._error = None
                if state.power:
                    self._sleep_started = time.monotonic()
                    if self._active_speed is None:
                        self._active_speed = self._speed
                    self._next_mode_at = 0.0
                else:
                    self._active_speed = None
        except DeviceError as exc:
            with self._lock:
                self._error = str(exc)

    def _do_set_speed(self, level: int) -> None:
        level = max(SPEED_MIN, min(SPEED_MAX, int(level)))
        device = self._device_or_none()
        with self._lock:
            self._speed = level
            power = self._power
            mode = self._mode
        if device is None:
            return
        if not power:
            # 便利交互：关机状态下选档位 = 开机并设档位
            self._do_set_power(True)
            device = self._device_or_none()
            if device is None:
                return
        try:
            if mode == MODE_NORMAL:
                state = device.set_speed(level)
                with self._lock:
                    self._active_speed = state.speed
                    self._error = None
            else:
                with self._lock:
                    self._next_mode_at = 0.0  # 让场景引擎立刻重算
                    self._error = None
        except DeviceError as exc:
            with self._lock:
                self._error = str(exc)

    def _do_set_oscillation(self, on: bool) -> None:
        device = self._device_or_none()
        if device is None:
            return
        try:
            state = device.set_oscillation(on)
            with self._lock:
                self._oscillation = state.oscillation
                self._error = None
        except DeviceError as exc:
            with self._lock:
                self._error = str(exc)

    def _do_set_angle(self, degrees: int) -> None:
        degrees = max(ANGLE_MIN, min(ANGLE_MAX, int(degrees)))
        device = self._device_or_none()
        if device is None:
            return
        try:
            state = device.set_angle(degrees)
            with self._lock:
                self._angle = state.angle
                self._oscillation = state.oscillation
                self._error = None
        except DeviceError as exc:
            with self._lock:
                self._error = str(exc)

    def _do_set_mode(self, mode: str) -> None:
        with self._lock:
            self._mode = mode
            self._next_mode_at = 0.0
            power = self._power
            speed = self._speed
        if mode == MODE_SLEEP:
            with self._lock:
                self._sleep_started = time.monotonic()
        device = self._device_or_none()
        if device is None or not power:
            return
        if mode == MODE_NORMAL:
            try:
                state = device.set_speed(speed)
                with self._lock:
                    self._active_speed = state.speed
                    self._error = None
            except DeviceError as exc:
                with self._lock:
                    self._error = str(exc)

    def _do_set_timer(self, minutes: int) -> None:
        with self._lock:
            if minutes <= 0:
                self._timer_end = None
                self._timer_total = None
            else:
                self._timer_total = float(minutes * 60)
                self._timer_end = time.monotonic() + self._timer_total

    # -- 后台引擎 -----------------------------------------------------------

    def _tick_timer(self) -> None:
        with self._lock:
            end = self._timer_end
            power = self._power
        if end is None:
            return
        if time.monotonic() >= end:
            with self._lock:
                self._timer_end = None
                self._timer_total = None
            if power:
                self._do_set_power(False)

    def _tick_mode_engine(self) -> None:
        with self._lock:
            power = self._power
            mode = self._mode
            if not power or mode == MODE_NORMAL:
                return
            if time.monotonic() < self._next_mode_at:
                return
            user_speed = self._speed
            sleep_started = self._sleep_started

        device = self._device_or_none()
        if device is None:
            return

        now = time.monotonic()
        if mode == MODE_NATURAL:
            target = compute_natural_speed(user_speed)
            interval = random.uniform(*NATURAL_INTERVAL_RANGE)
        else:  # MODE_SLEEP
            elapsed = now - (sleep_started or now)
            target = compute_sleep_speed(user_speed, elapsed)
            interval = 10.0

        try:
            with self._lock:
                current = self._active_speed
            if current != target:
                state = device.set_speed(target)
                with self._lock:
                    self._active_speed = state.speed
                    self._error = None
        except DeviceError as exc:
            with self._lock:
                self._error = str(exc)
        finally:
            with self._lock:
                self._next_mode_at = now + interval

    def _tick_poll(self) -> None:
        with self._lock:
            device = self._device
            if device is None or not isinstance(device, LineProtocolDevice):
                return
            if time.monotonic() < self._next_poll:
                return
            self._next_poll = time.monotonic() + POLL_INTERVAL
        try:
            device.query_state()
            with self._lock:
                self._poll_fails = 0
        except DeviceError as exc:
            with self._lock:
                self._poll_fails += 1
                fails = self._poll_fails
                if fails >= POLL_FAIL_LIMIT:
                    self._device = None
                    self._active_speed = None
                    self._error = f"设备失去响应：{exc}"
                    logger.warning("设备掉线: %s", exc)

    # -- 状态快照 -----------------------------------------------------------

    def get_snapshot(self) -> Snapshot:
        with self._lock:
            device = self._device
            remaining = None
            if self._timer_end is not None:
                remaining = max(0.0, self._timer_end - time.monotonic())
            return Snapshot(
                power=self._power,
                speed=self._speed,
                oscillation=self._oscillation,
                angle=self._angle,
                mode=self._mode,
                active_speed=self._active_speed,
                timer_remaining=remaining,
                timer_total=self._timer_total,
                mute=self._mute,
                connected=device is not None and device.is_connected,
                connecting=self._connecting,
                device_label=device.label if device else "未连接",
                firmware=device.firmware if device else None,
                error=self._error,
            )
