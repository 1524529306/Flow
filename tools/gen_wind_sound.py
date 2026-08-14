# -*- coding: utf-8 -*-
"""离线生成 3 档风声循环样本（棕噪底 + 带通呼啸 + 四阶低通）。

输出：assets/audio/wind_1.wav / wind_2.wav / wind_3.wav（16bit/22050Hz/2s）
档位差异：低通截止频率、呼啸峰中心/强度、阵风深度、峰值音量逐档递增 ——
1 档轻柔低语，3 档明显呼啸但不刺耳。纯 numpy 合成，无版权问题。

设计要点（v2.2.3 重制）：
- 棕噪底 1/f^1.8 取代粉噪 1/f^0.5 —— 高频自然衰减，无静态嘶嘶感
- 带通峰模拟风扇格栅气流共振（whoosh），取代旧版"拉平频谱"的粗暴做法
- 四阶 Butterworth 低通彻底砍掉 >cutoff 的高频残留，杜绝刺耳
- 阵风包络频率取 0.5/1.0 Hz（2 秒内整数周期），循环接缝无爆音
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SR = 22050
DUR = 2.0
OUT = Path(__file__).resolve().parent.parent / "assets" / "audio"

#                     低通截止   呼啸峰中心  呼啸增益  阵风深度  峰值
SPECS = (
    ("wind_1.wav",    2500,       500,       0.00,    0.10,    0.20),
    ("wind_2.wav",    4000,       900,       0.35,    0.18,    0.32),
    ("wind_3.wav",    6000,      1400,       0.65,    0.25,    0.50),
)


def wind_noise(n: int, cutoff: float, whoosh_center: float,
               whoosh_gain: float, rng: np.random.Generator) -> np.ndarray:
    """棕噪底（加法叠加带通呼啸）+ 四阶低通 → 柔顺但有层次的风声。

    加法叠加：whoosh 用独立噪声源经带通滤波后叠加到棕噪底上，
    避免乘法模式下高频被低频淹没的问题。
    """
    freqs = np.arange(n // 2 + 1, dtype=np.float64)

    # 1. 棕噪底：1/f^1.5（比粉噪 1/f^0.5 陡得多，高频自然衰减）
    x1 = rng.standard_normal(n)
    base_gain = 1.0 / (freqs + 1.0) ** 1.5
    base = np.fft.irfft(np.fft.rfft(x1) * base_gain, n)

    # 2. 带通呼啸：独立噪声源 → 高斯带通 → 叠加（模拟风扇格栅气流共振）
    if whoosh_gain > 0:
        x2 = rng.standard_normal(n)
        bw = whoosh_center * 0.5
        bp = np.exp(-((freqs - whoosh_center) / bw) ** 2)
        whoosh = np.fft.irfft(np.fft.rfft(x2) * bp, n)
        # 归一化到与 base 同 RMS 后乘增益，保证跨档位可比
        whoosh = whoosh / (np.std(whoosh) + 1e-9) * np.std(base) * whoosh_gain
        sig = base + whoosh
    else:
        sig = base

    # 3. 四阶 Butterworth 低通：截止以上陡降 24dB/oct，杜绝刺耳高频残留
    spec = np.fft.rfft(sig)
    lp = 1.0 / (1.0 + (freqs / cutoff) ** 4)
    return np.fft.irfft(spec * lp, n)


def gust(t: np.ndarray, depth: float, rng: np.random.Generator) -> np.ndarray:
    """阵风包络：0.5Hz 与 1.0Hz 正弦叠加（2 秒内整数周期，循环无缝）。"""
    p = rng.uniform(0, 2 * math.pi)
    return (0.8 + depth * (0.15 * np.sin(2 * math.pi * 0.5 * t + p)
                           + 0.10 * np.sin(2 * math.pi * 1.0 * t + p * 1.7)))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    n = int(SR * DUR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(20260813)
    for name, cutoff, wcenter, wgain, depth, peak in SPECS:
        sig = wind_noise(n, cutoff, wcenter, wgain, rng) * gust(t, depth, rng)
        sig = sig / (np.max(np.abs(sig)) + 1e-9) * peak
        pcm = (sig * 32767).astype(np.int16)
        path = OUT / name
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        print(f"生成 {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
