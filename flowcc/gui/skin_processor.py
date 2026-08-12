"""第三方风扇皮肤自动适配引擎。

任意一张「立式风扇」图片（纯色/近纯色背景）经以下流水线处理：
1. 裁掉底部 12%（常见水印区）；
2. 从四角 flood-fill 去背景（容忍度内视为背景），得到透明 PNG；
3. 按 alpha 包围盒裁剪，得到风扇主体；
4. 在上 70% 区域按「最宽行」启发式定位扇头圆心与半径，
   供挂件叠加旋转叶影动画。

处理结果缓存为 PNG + JSON，上传一次、永久复用。
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

WATERMARK_CROP = 0.88      # 保留上 88% 高度
BG_THRESH = 60             # 背景 flood-fill 容忍度
HEAD_BAND = 0.70           # 扇头搜索区域（主体高度的上 70%）
MARK = (255, 0, 255)


def _row_extent(alpha_row):
    left = next((x for x, a in enumerate(alpha_row) if a > 0), None)
    if left is None:
        return None
    right = next((x for x in range(len(alpha_row) - 1, -1, -1)
                  if alpha_row[x] > 0), left)
    return left, right


def process_skin(src_path, out_png, out_meta) -> dict:
    """处理一张皮肤图，写出透明 PNG 与元数据，返回元数据 dict。"""
    img = Image.open(src_path).convert("RGB")
    w, h = img.size
    img = img.crop((0, 0, w, int(h * WATERMARK_CROP)))
    w, h = img.size

    # -- 去背景：四角 flood-fill 标记为背景 --
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if img.getpixel(seed) != MARK:
            ImageDraw.floodfill(img, seed, MARK, thresh=BG_THRESH)

    rgba = img.convert("RGBA")
    px = rgba.load()
    for y in range(h):
        for x in range(w):
            r, g, b, _ = px[x, y]
            if (r, g, b) == MARK:
                px[x, y] = (0, 0, 0, 0)

    # -- 包围盒裁剪 --
    bbox = rgba.getbbox()
    if not bbox:
        raise ValueError("未检测到风扇主体：背景与主体对比不足")
    rgba = rgba.crop(bbox)
    fw, fh = rgba.size
    alpha = list(rgba.split()[3].getdata())
    rows = [alpha[y * fw:(y + 1) * fw] for y in range(fh)]

    # -- 扇头定位：上 70% 内最宽 alpha 行 --
    best_w, best_y = 0, 0
    for y in range(0, int(fh * HEAD_BAND)):
        ext = _row_extent(rows[y])
        if ext and ext[1] - ext[0] > best_w:
            best_w = ext[1] - ext[0]
            best_y = y
    if best_w < 8:
        raise ValueError("未检测到扇头区域")

    # 以最宽行附近宽度 >= 92% 的行取平均，稳定圆心
    ys = ls = rs = n = 0
    lo = max(0, best_y - int(best_w * 0.4))
    hi = min(int(fh * HEAD_BAND), best_y + int(best_w * 0.4))
    for y in range(lo, hi):
        ext = _row_extent(rows[y])
        if ext and ext[1] - ext[0] >= best_w * 0.92:
            ys += y
            ls += ext[0]
            rs += ext[1]
            n += 1
    if n == 0:
        n, ys = 1, best_y
        ext = _row_extent(rows[best_y]) or (0, fw)
        ls, rs = ext
    head_cx = (ls / n + rs / n) / 2
    head_cy = ys / n
    head_r = best_w / 2

    rgba.save(out_png)
    meta = {
        "png": str(out_png),
        "head": [round(head_cx, 1), round(head_cy, 1), round(head_r, 1)],
        "size": [fw, fh],
    }
    Path(out_meta).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta
