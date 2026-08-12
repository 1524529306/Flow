"""传输层端到端测试：用 FakeSerial / 本地 TCP 服务模拟固件，
验证 SerialFanDevice / WifiFanDevice 的完整命令事务链路，
确保后期接入真实硬件时软件侧行为正确。
"""
import socket
import threading
import unittest

from flowcc.device.base import DeviceError
from flowcc.device.serialdev import SerialFanDevice
from flowcc.device.wifidev import WifiFanDevice


class FakeFirmware:
    """协议 v1.1 的固件行为模拟（与 esp32_fan.ino 逐条对应）。"""

    def __init__(self):
        self.state = {"pwr": 0, "spd": 1, "osc": 0, "ang": 90}

    def state_line(self):
        return "STATE pwr={pwr} spd={spd} osc={osc} ang={ang}".format(**self.state)

    def handle(self, line):
        """返回应答行列表。"""
        parts = line.split()
        if not parts:
            return []
        cmd, arg = parts[0], (parts[1] if len(parts) > 1 else "")
        if cmd == "PING":
            return ["PONG"]
        if cmd == "STATE?":
            return ["OK STATE?", self.state_line()]
        if cmd == "PWR":
            if arg not in ("0", "1"):
                return ["ERR PWR BADARG"]
            self.state["pwr"] = int(arg)
            return ["OK PWR", self.state_line()]
        if cmd == "SPD":
            if arg not in ("1", "2", "3"):
                return ["ERR SPD BADARG"]
            self.state["spd"] = int(arg)
            return ["OK SPD", self.state_line()]
        if cmd == "OSC":
            if arg not in ("0", "1"):
                return ["ERR OSC BADARG"]
            self.state["osc"] = int(arg)
            return ["OK OSC", self.state_line()]
        if cmd == "ANG":
            if not arg.isdigit() or not 0 <= int(arg) <= 180:
                return ["ERR ANG BADARG"]
            self.state["ang"] = int(arg)
            self.state["osc"] = 0  # 手动摆头退出自动摇头
            return ["OK ANG", self.state_line()]
        return [f"ERR {cmd} UNSUPPORTED"]


class FakeSerial(FakeFirmware):
    """兼容 pyserial.Serial 构造与读写接口的假串口。"""

    def __init__(self, port="", baudrate=115200, timeout=0.2,
                 write_timeout=1.0, silent=False):
        super().__init__()
        self.timeout = timeout
        self._out = bytearray()
        self._silent = silent
        if not silent:
            self._out += b"HELLO FLOWCC 1.3\n"

    def write(self, data):
        if not self._silent:
            for line in data.decode("ascii").splitlines():
                for reply in self.handle(line.strip()):
                    self._out += (reply + "\n").encode("ascii")
        return len(data)

    def flush(self):
        pass

    def read(self, n):
        chunk = bytes(self._out[:n])
        del self._out[:n]
        return chunk

    def reset_input_buffer(self):
        self._out.clear()

    def close(self):
        pass


class TestSerialEndToEnd(unittest.TestCase):
    """SerialFanDevice + 模拟固件 的完整链路。"""

    def _device(self, **kw):
        dev = SerialFanDevice("FAKE", serial_impl=lambda **a: FakeSerial(**a, **kw))
        dev.connect()
        return dev

    def test_connect_reads_hello_and_state(self):
        dev = self._device()
        self.assertEqual(dev.firmware, "1.3")
        self.assertTrue(dev.is_connected)
        state = dev.query_state()
        self.assertFalse(state.power)
        self.assertEqual(state.speed, 1)

    def test_full_control_roundtrip(self):
        dev = self._device()
        self.assertTrue(dev.set_power(True).power)
        self.assertEqual(dev.set_speed(3).speed, 3)
        dev.set_oscillation(True)
        state = dev.set_angle(120)
        self.assertEqual(state.angle, 120)
        self.assertFalse(state.oscillation)  # 手动摆头退出自动摇头
        dev.disconnect()
        self.assertFalse(dev.is_connected)

    def test_silent_device_times_out(self):
        dev = SerialFanDevice(
            "FAKE", serial_impl=lambda **a: FakeSerial(**a, silent=True))
        with self.assertRaises(DeviceError):
            dev.connect()
        self.assertFalse(dev.is_connected)


class ProtoTcpServer(threading.Thread):
    """本地 TCP 服务，模拟 WiFi 固件。"""

    def __init__(self):
        super().__init__(daemon=True)
        self.firmware = FakeFirmware()
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self._conn = None

    def run(self):
        try:
            self._conn, _ = self.sock.accept()
        except OSError:
            return
        self._conn.sendall(b"HELLO FLOWCC 1.3\n")
        buffer = b""
        while True:
            try:
                chunk = self._conn.recv(256)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                for reply in self.firmware.handle(line.decode().strip()):
                    try:
                        self._conn.sendall((reply + "\n").encode())
                    except OSError:
                        return

    def stop(self):
        try:
            if self._conn:
                self._conn.close()
            self.sock.close()
        except OSError:
            pass


class TestWifiEndToEnd(unittest.TestCase):
    """WifiFanDevice + 本地 TCP 模拟固件 的完整链路。"""

    def test_wifi_control_roundtrip(self):
        server = ProtoTcpServer()
        server.start()
        dev = WifiFanDevice("127.0.0.1", server.port)
        try:
            dev.connect()
            self.assertEqual(dev.firmware, "1.3")
            self.assertTrue(dev.set_power(True).power)
            self.assertEqual(dev.set_speed(2).speed, 2)
            self.assertEqual(dev.set_angle(45).angle, 45)
            state = dev.query_state()
            self.assertTrue(state.power)
        finally:
            dev.disconnect()
            server.stop()

    def test_wifi_unreachable(self):
        dev = WifiFanDevice("127.0.0.1", 1)  # 端口 1 必无服务
        with self.assertRaises(DeviceError):
            dev.connect()


if __name__ == "__main__":
    unittest.main()
