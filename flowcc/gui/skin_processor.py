"""皮肤 PNG 严格校验器（v2.0.0 设计）。

设计原则：皮肤 PNG 必须由作者在外部工具（remove.bg / Photoshop / Figma / GIMP）
提前导出为 RGBA 含透明通道。本模块不做任何背景移除，只做：
  1. 校验格式（必须是 RGBA）
  2. 校验透明像素比例（必须有实质透明）
  3. 检测扇头包围盒
  4. 缩放到目标尺寸

任何不符合规范的输入都会抛 ValueError，错误信息指向《皮肤制作指南》。
离线批量生成请使用 ``tools/build_skins.py``。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

from PIL import Image

# 校验阈值
MIN_TRANSPARENT_RATIO = 0.05   # 至少 5% 透明像素，否则视为「整图实心」
MIN_HEAD_RADIUS = 40            # 最小扇头半径（像素）
TARGET_HEAD_RADIUS = 100        # 缩放目标扇头半径


class SkinFormatError(ValueError):
    """皮肤 PNG 不符合规范的明确错误。"""


def _load_rgba(src: str | Path) -> Image.Image:
    """读取并强制转为 RGBA。"""
    img = Image.open(src)
    img.load()
    if img.mode != "RGBA":
        raise SkinFormatError(
            f"皮肤 PNG 必须是 RGBA 含透明通道（当前 mode={img.mode}）。"
            "请用 remove.bg / Photoshop / Figma 导出时勾选「透明背景」。"
            "详见 docs/SKIN_GUIDE.md。"
        )
    return img


def _check_transparency(img: Image.Image) -> None:
    """检查透明像素占比。"""
    alpha = img.split()[3]
    hist = alpha.histogram()
    total = img.size[0] * img.size[1]
    transparent = hist[0] + sum(hist[1:64])  # 全透明 + 近透明
    ratio = transparent / total if total else 0
    if ratio < MIN_TRANSPARENT_RATIO:
        raise SkinFormatError(
            f"皮肤 PNG 缺少透明背景（透明像素仅 {ratio:.1%}）。"
            "请确认导出时勾选了「透明背景」选项。"
            "详见 docs/SKIN_GUIDE.md。"
        )


def _detect_head_bbox(img: Image.Image) -> Tuple[int, int, int, int]:
    """检测风扇主体（不透明像素）的最小包围盒。"""
    alpha = img.split()[3]
    mask = alpha.point(lambda a: 255 if a > 200 else 0)
    bbox = mask.getbbox()
    if not bbox:
        raise SkinFormatError("未检测到风扇主体（整张图近乎全透明）。")
    x0, y0, x1, y1 = bbox
    bw, bh = x1 - x0, y1 - y0
    if bw < MIN_HEAD_RADIUS * 2 or bh < MIN_HEAD_RADIUS * 2:
        raise SkinFormatError(
            f"主体尺寸过小（{bw}×{bh}），无法定位扇头。"
            "请用更高分辨率或更紧凑的画布重导出。"
        )
    return x0, y0, x1, y1


def _auto_fit(img: Image.Image) -> Tuple[Image.Image, Tuple[int, int, int]]:
    """根据包围盒自适应缩放，返回 (裁剪后图, head_center_x, head_center_y, radius)。"""
    x0, y0, x1, y1 = _detect_head_bbox(img)
    cropped = img.crop((x0, y0, x1, y1))
    bw, bh = cropped.size
    # 自适应：让包围盒内切圆达到 TARGET_HEAD_RADIUS
    scale = (TARGET_HEAD_RADIUS * 2) / min(bw, bh)
    if scale != 1.0:
        new_size = (int(round(bw * scale)), int(round(bh * scale)))
        cropped = cropped.resize(new_size, Image.LANCZOS)
    # 扇头 = 包围盒的圆心，水平居中，垂直偏上 1/3
    cx = cropped.size[0] // 2
    cy = cropped.size[1] // 3
    r = TARGET_HEAD_RADIUS
    return cropped, (cx, cy, r)


def process_skin(src: str | Path,
                 out_png: str | Path,
                 out_meta: str | Path) -> Dict[str, Any]:
    """校验皮肤 PNG 并生成缓存，返回 head 定位元数据。

    参数：
        src: 源 PNG 路径（RGBA 含透明通道）
        out_png: 处理后 PNG 输出路径（缩放后版本，可直接用于渲染）
        out_meta: 元数据 JSON 输出路径（head 中心与半径）

    返回：
        dict，含 'png' / 'head' (cx, cy, r) / 'size' (w, h)

    抛出：
        SkinFormatError: 不符合规范的输入
    """
    img = _load_rgba(src)
    _check_transparency(img)
    cropped, head = _auto_fit(img)
    fw, fh = cropped.size
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    cropped.save(out_png, format="PNG", optimize=True)
    meta = {
        "png": str(out_png),
        "head": list(head),
        "size": [fw, fh],
        "version": 2,
    }
    Path(out_meta).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return meta