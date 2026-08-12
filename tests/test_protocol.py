"""协议编解码单元测试。"""
import unittest

from flowcc import protocol as P


class TestEncode(unittest.TestCase):
    def test_encode_commands(self):
        self.assertEqual(P.encode_power(True), "PWR 1\n")
        self.assertEqual(P.encode_power(False), "PWR 0\n")
        self.assertEqual(P.encode_speed(2), "SPD 2\n")
        self.assertEqual(P.encode_oscillation(True), "OSC 1\n")
        self.assertEqual(P.encode_query(), "STATE?\n")
        self.assertEqual(P.encode_ping(), "PING\n")

    def test_encode_speed_bounds(self):
        self.assertEqual(P.encode_speed(P.SPEED_MIN), "SPD 1\n")
        self.assertEqual(P.encode_speed(P.SPEED_MAX), "SPD 3\n")
        with self.assertRaises(ValueError):
            P.encode_speed(0)
        with self.assertRaises(ValueError):
            P.encode_speed(4)


class TestParse(unittest.TestCase):
    def test_parse_ok(self):
        msg = P.parse_line("OK PWR")
        self.assertIs(msg.kind, P.MessageKind.OK)
        self.assertEqual(msg.command, "PWR")

    def test_parse_err(self):
        msg = P.parse_line("ERR SPD BADARG")
        self.assertIs(msg.kind, P.MessageKind.ERR)
        self.assertEqual(msg.command, "SPD")
        self.assertEqual(msg.error_code, "BADARG")

    def test_parse_state(self):
        msg = P.parse_line("STATE pwr=1 spd=2 osc=0")
        self.assertIs(msg.kind, P.MessageKind.STATE)
        self.assertTrue(msg.state.power)
        self.assertEqual(msg.state.speed, 2)
        self.assertFalse(msg.state.oscillation)

    def test_parse_pong_and_hello(self):
        self.assertIs(P.parse_line("PONG").kind, P.MessageKind.PONG)
        msg = P.parse_line("HELLO FLOWCC 1.0")
        self.assertIs(msg.kind, P.MessageKind.HELLO)
        self.assertEqual(msg.version, "1.0")

    def test_parse_unknown_never_raises(self):
        for line in ("", "   ", "WHAT EVER", "STATE pwr=1", "OK",
                     "STATE pwr=x spd=y osc=z", "STATE pwr=1 spd=9 osc=0"):
            msg = P.parse_line(line)
            self.assertIsNotNone(msg)
        # 大小写不敏感的帧头
        self.assertIs(P.parse_line("pong").kind, P.MessageKind.PONG)

    def test_state_roundtrip(self):
        state = P.FanState(power=True, speed=3, oscillation=True)
        msg = P.parse_line("STATE " + state.encode_payload())
        self.assertEqual(msg.state, state)


if __name__ == "__main__":
    unittest.main()
