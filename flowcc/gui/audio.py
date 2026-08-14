# -*- coding: utf-8 -*-
"""风声播放封装 —— Windows 用 winsound 循环播放，零第三方依赖。

音量不运行时调节：三档音量已在离线生成样本时写死（wind_1/2/3.wav
峰值递增），切档即切文件；静音 = 停止播放。
macOS / Linux 无 winsound，自动降级为静默（不报错、不打扰）。
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_PLAYING_KEY = Tuple[bool, int]


def _resource_dir() -> str:
    """assets/audio 目录（兼容 PyInstaller 打包路径与源码运行）。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, "assets", "audio")
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "assets", "audio")


class WindAudio:
    """按电源/档位状态驱动风声循环播放。线程安全（GUI 线程单点调用）。"""

    def __init__(self) -> None:
        self._muted = False
        self._playing: Optional[_PLAYING_KEY] = None
        try:
            import winsound  # type: ignore[import-not-found]
            self._ws = winsound
        except ImportError:
            self._ws = None

    @property
    def available(self) -> bool:
        return self._ws is not None

    def set_muted(self, muted: bool) -> None:
        self._muted = muted
        if muted:
            self._stop()

    def update(self, power: bool, speed: int) -> None:
        """按当前状态播放 / 切换 / 停止风声。"""
        if not self._ws:
            return
        want_on = power and speed >= 1
        if self._muted or not want_on:
            self._stop()
            return
        key: _PLAYING_KEY = (power, speed)
        if key == self._playing:
            return
        self._stop()
        path = os.path.join(_resource_dir(), f"wind_{speed}.wav")
        try:
            self._ws.PlaySound(
                path,
                self._ws.SND_FILENAME | self._ws.SND_ASYNC | self._ws.SND_LOOP,
            )
            self._playing = key
        except (RuntimeError, OSError):
            logger.warning("播放风声失败（可能无音频设备）", exc_info=True)
            self._playing = None

    def _stop(self) -> None:
        if self._ws:
            try:
                self._ws.PlaySound(None, 0)
            except RuntimeError:
                pass
        self._playing = None
