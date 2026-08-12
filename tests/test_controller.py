"""控制器与模拟设备集成测试（无需任何硬件）。"""
import time
import unittest

from flowcc.controller import (
    MODE_NATURAL,
    MODE_NORMAL,
    MODE_SLEEP,
    FanController,
    compute_natural_speed,
    compute_sleep_speed,
)
from flowcc.protocol import SPEED_MAX, SPEED_MIN


def wait_until(predicate, timeout=3.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestModeMath(unittest.TestCase):
    """场景引擎的纯函数部分。"""

    def test_sleep_speed_drops_over_time(self):
        self.assertEqual(compute_sleep_speed(3, 0), 3)
        self.assertEqual(compute_sleep_speed(3, 19 * 60), 3)
        self.assertEqual(compute_sleep_speed(3, 20 * 60), 2)
        self.assertEqual(compute_sleep_speed(3, 40 * 60), 1)
        self.assertEqual(compute_sleep_speed(3, 10 * 3600), 1)  # 不会低于 1 档
        self.assertEqual(compute_sleep_speed(1, 40 * 60), 1)

    def test_natural_speed_within_bounds(self):
        for user_speed in range(SPEED_MIN, SPEED_MAX + 1):
            for _ in range(200):
                value = compute_natural_speed(user_speed)
                self.assertGreaterEqual(value, max(SPEED_MIN, user_speed - 1))
                self.assertLessEqual(value, min(SPEED_MAX, user_speed + 1))


class TestControllerWithMock(unittest.TestCase):
    """控制器 + 模拟设备 的端到端行为。"""

    def setUp(self):
        self.controller = FanController()
        self.controller.start()
        self.controller.connect_mock()

    def tearDown(self):
        self.controller.stop()

    def snap(self):
        return self.controller.get_snapshot()

    def test_initial_state(self):
        snap = self.snap()
        self.assertTrue(snap.connected)
        self.assertEqual(snap.device_label, "模拟设备")
        self.assertFalse(snap.power)

    def test_power_on_off(self):
        self.controller.set_power(True)
        self.assertTrue(wait_until(lambda: self.snap().power))
        self.controller.set_power(False)
        self.assertTrue(wait_until(lambda: not self.snap().power))

    def test_set_speed_while_off_turns_power_on(self):
        self.controller.set_speed(3)
        self.assertTrue(wait_until(lambda: self.snap().power))
        self.assertTrue(wait_until(lambda: self.snap().active_speed == 3))

    def test_oscillation(self):
        self.controller.set_oscillation(True)
        self.assertTrue(wait_until(lambda: self.snap().oscillation))
        self.controller.set_oscillation(False)
        self.assertTrue(wait_until(lambda: not self.snap().oscillation))

    def test_manual_angle_stops_oscillation(self):
        self.controller.set_oscillation(True)
        self.assertTrue(wait_until(lambda: self.snap().oscillation))
        self.controller.set_angle(30)
        self.assertTrue(wait_until(lambda: self.snap().angle == 30))
        self.assertFalse(self.snap().oscillation)
        # 越界值会被夹取到合法范围
        self.controller.set_angle(999)
        self.assertTrue(wait_until(lambda: self.snap().angle == 180))

    def test_timer_turns_power_off(self):
        self.controller.set_power(True)
        self.assertTrue(wait_until(lambda: self.snap().power))
        # 绕过分钟粒度，直接设一个极短的定时用于测试
        with self.controller._lock:
            self.controller._timer_total = 0.5
            self.controller._timer_end = time.monotonic() + 0.5
        self.assertTrue(wait_until(lambda: not self.snap().power, timeout=5.0))
        self.assertIsNone(self.snap().timer_remaining)

    def test_timer_cancel(self):
        self.controller.set_timer_minutes(30)
        self.assertTrue(wait_until(
            lambda: self.snap().timer_remaining is not None))
        self.controller.set_timer_minutes(0)
        self.assertTrue(wait_until(
            lambda: self.snap().timer_remaining is None))

    def test_natural_mode_keeps_speed_in_range(self):
        self.controller.set_power(True)
        self.controller.set_speed(2)
        self.assertTrue(wait_until(lambda: self.snap().power))
        self.controller.set_mode(MODE_NATURAL)
        seen = set()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            snap = self.snap()
            if snap.active_speed:
                self.assertGreaterEqual(snap.active_speed, 1)
                self.assertLessEqual(snap.active_speed, 3)
                seen.add(snap.active_speed)
            time.sleep(0.1)
        self.assertTrue(seen, "自然风模式下应观察到输出档位")

    def test_switch_back_to_normal_restores_user_speed(self):
        self.controller.set_power(True)
        self.controller.set_speed(3)
        self.controller.set_mode(MODE_NATURAL)
        time.sleep(0.3)
        self.controller.set_mode(MODE_NORMAL)
        self.assertTrue(wait_until(lambda: self.snap().mode == MODE_NORMAL))
        self.assertTrue(wait_until(lambda: self.snap().active_speed == 3))

    def test_disconnect_and_reconnect(self):
        self.controller.disconnect()
        self.assertTrue(wait_until(lambda: not self.snap().connected))
        self.controller.connect_mock()
        self.assertTrue(wait_until(lambda: self.snap().connected))


if __name__ == "__main__":
    unittest.main()
