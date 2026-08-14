# -*- coding: utf-8 -*-
"""WindAudio 单元测试：用 mock winsound 记录调用序列。"""
import sys
import types
import unittest
from unittest import mock

with mock.patch.dict(sys.modules, {}):
    # 先移除可能已缓存的真 winsound，保证 mock 生效
    sys.modules.pop("winsound", None)

import flowcc.gui.audio as audio_mod  # noqa: E402


def _make_fake_ws():
    ws = types.ModuleType("winsound")
    ws.SND_FILENAME = 0x20000
    ws.SND_ASYNC = 0x1
    ws.SND_LOOP = 0x8
    ws.calls = []

    def play(*args):
        ws.calls.append(args)

    ws.PlaySound = play
    return ws


class WindAudioTest(unittest.TestCase):
    def setUp(self):
        self.ws = _make_fake_ws()
        self.patcher = mock.patch.dict(sys.modules, {"winsound": self.ws})
        self.patcher.start()
        import importlib
        importlib.reload(audio_mod)
        self.audio = audio_mod.WindAudio()

    def tearDown(self):
        self.patcher.stop()
        sys.modules.pop("winsound", None)

    def test_power_on_plays_matching_track(self):
        self.audio.update(True, 2)
        last = self.ws.calls[-1]
        self.assertIn("wind_2.wav", last[0])
        self.assertEqual(last[1], 0x20000 | 0x1 | 0x8)

    def test_same_state_does_not_restart(self):
        self.audio.update(True, 1)
        n = len(self.ws.calls)
        self.audio.update(True, 1)
        self.audio.update(True, 1)
        self.assertEqual(len(self.ws.calls), n)

    def test_speed_change_switches_track(self):
        self.audio.update(True, 1)
        self.audio.update(True, 3)
        last = self.ws.calls[-1]
        self.assertIn("wind_3.wav", last[0])

    def test_power_off_stops(self):
        self.audio.update(True, 2)
        self.audio.update(False, 0)
        self.assertEqual(self.ws.calls[-1], (None, 0))

    def test_mute_blocks_playback(self):
        self.audio.set_muted(True)
        n = len(self.ws.calls)
        self.audio.update(True, 3)
        # 静音后只允许出现 stop（PlaySound(None, 0)），不允许播放文件
        plays = [c for c in self.ws.calls[n:] if c[0] is not None]
        self.assertEqual(plays, [])

    def test_unmute_resumes(self):
        self.audio.set_muted(True)
        self.audio.update(True, 2)
        self.audio.set_muted(False)
        self.audio.update(True, 2)
        self.assertIn("wind_2.wav", self.ws.calls[-1][0])


if __name__ == "__main__":
    unittest.main()
