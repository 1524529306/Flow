"""第三方风扇皮肤自动适配引擎（v1.4.1：增强对渐变背景的兼容性）。

任意一张「立式风扇」图片（纯色/近纯色/渐变背景）经以下流水线处理：
1. 裁掉底部 12%（常见水印区）；
2. 沿四条边多点采样、聚类识别「主要背景色」；
3. 从四角对「接近背景色」的种子点做 flood-fill，标记背景为魔法色；
4. 二次过滤：边缘/半透明像素若 RGB 接近背景色，强制 alpha=0
   （解决渐变背景残留与粉边色差）；
5. alpha 二值化保留主体硬边缘；
6. 按 alpha 包围盒裁剪，得到风扇主体；
7. 在上 70% 区域按「最宽行」启发式定位扇头圆心与半径，
   供挂件叠加旋转叶影动画。

处理结果缓存为 PNG + JSON，上传一次、永久复用。
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

WATERMARK_CROP = 0.88      # 保留上 88% 高度
BG_THRESH = 100            # flood-fill 容忍度（60→100：让渐变更连贯）
HEAD_BAND = 0.70           # 扇头搜索区域（主体高度的上 70%）
MARK = (255, 0, 255)       # 背景标记魔法色
EDGE_ALPHA_DIST = 40       # 边缘清理：像素与背景色距离阈值（RGB 空间）
ALPHA_KEEP = 128           # 最终 alpha 二值化阈值（96→128：保留硬主体边缘）
EDGE_SAMPLE_FRACTIONS = (0.0, 0.15, 0.30, 0.50, 0.70, 0.85, 1.0)


def _row_extent(alpha_row):
    left = next((x for x, a in enumerate(alpha_row) if a > 0), None)
    if left is None:
        return None
    right = next((x for x in range(len(alpha_row) - 1, -1, -1)
                  if alpha_row[x] > 0), left)
    return left, right


def _color_dist_sq(a, b):
    """RGB 平方距离。"""
    dr = a[0] - b[0]
    dg = a[1] - b[1]
    db = a[2] - b[2]
    return dr * dr + dg * dg + db * db


def _edge_samples(img) -> list[tuple[int, int, tuple]]:
    """沿四条边采样若干像素，返回 [(x, y, rgb), ...]。

    上/下边取 7 个点（含两端），左/右边各取 5 个点（不含端点避免重复）。
    """
    w, h = img.size
    pts: list[tuple[int, int]] = []
    for f in EDGE_SAMPLE_FRACTIONS:
        pts.append((int(w * f), 0))
        pts.append((int(w * f), h - 1))
    for f in EDGE_SAMPLE_FRACTIONS[1:-1]:
        pts.append((0, int(h * f)))
        pts.append((w - 1, int(h * f)))
    samples: list[tuple[int, int, tuple]] = []
    for x, y in pts:
        if 0 <= x < w and 0 <= y < h:
            samples.append((x, y, img.getpixel((x, y))[:3]))
    return samples


def _cluster_background(samples, merge_dist_sq: int = 35 * 35 * 3) -> tuple | None:
    """把边缘采样按颜色距离聚类，返回最大簇的均值 RGB。"""
    if not samples:
        return None
    clusters: list[dict] = []
    for _, _, rgb in samples:
        merged = False
        for cl in clusters:
            if _color_dist_sq(cl["c"], rgb) < merge_dist_sq:
                cl["n"] += 1
                # 增量更新均值
                cl["c"] = tuple(
                    int(cl["c"][i] + (rgb[i] - cl["c"][i]) / cl["n"])
                    for i in range(3)
                )
                merged = True
                break
        if not merged:
            clusters.append({"c": rgb, "n": 1})
    if not clusters:
        return None
    clusters.sort(key=lambda c: -c["n"])
    return clusters[0]["c"]


def _flood_bg(img, bg_color) -> None:
    """从四个角出发，仅对 RGB 接近 bg_color 的种子点做 flood-fill。

    这样可以避免「主体像素恰好在角落」时把整图标成背景；
    同时把 BG_THRESH 适度放大到 100，让渐变背景的相邻色仍能连通。
    """
    w, h = img.size
    # 仅当种子像素本身属于「背景色簇」时启动 flood-fill
    seed_dist_sq = (BG_THRESH * 2) ** 2 * 3
    for seed in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        seed_rgb = img.getpixel(seed)[:3]
        if img.getpixel(seed) == MARK:
            continue
        if _color_dist_sq(seed_rgb, bg_color) < seed_dist_sq:
            ImageDraw.floodfill(img, seed, MARK, thresh=BG_THRESH)


def _clean_edge_alpha(rgba, bg_color) -> Image.Image:
    """抗锯齿边缘二次过滤：清理 alpha 处于过渡带的像素，去粉边/渐变残留。

    关键设计：**只清理 alpha 128~200 之间的过渡像素**：
    - alpha=255：核心主体像素，不动（保护"白主体+浅灰底"场景）
    - alpha=0：已被 flood-fill 清掉的背景，不动
    - alpha 1~127：已经被 ALPHA_KEEP=128 二值化清掉了，这里不会再遇到
    - alpha 128~200：抗锯齿边缘，颜色已被背景"染色"，按背景色距离清理
    这样既能去粉边/渐变残留，又不误伤主体；flood-fill 局部盲区靠 flood
    自身的多点种子部分缓解，深层湖用形态学后续步骤补刀。
    """
    bg_r, bg_g, bg_b = bg_color
    px = rgba.load()
    w, h = rgba.size
    soft_sq = (EDGE_ALPHA_DIST * 2) ** 2 * 3
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if (r, g, b) == MARK:
                px[x, y] = (0, 0, 0, 0)
                continue
            # 只清理 alpha 处于过渡带的边缘像素（抗锯齿/渐变残留）
            if 128 <= a < 200:
                dr = r - bg_r
                dg = g - bg_g
                db = b - bg_b
                if (dr * dr + dg * dg + db * db) < soft_sq:
                    px[x, y] = (r, g, b, 0)
    return rgba


def process_skin(src_path, out_png, out_meta) -> dict:
    """处理一张皮肤图，写出透明 PNG 与元数据，返回元数据 dict。"""
    img = Image.open(src_path).convert("RGB")
    w, h = img.size
    img = img.crop((0, 0, w, int(h * WATERMARK_CROP)))
    w, h = img.size

    # -- 边缘多点采样聚类识别「主要背景色」--
    samples = _edge_samples(img)
    bg_color = _cluster_background(samples) or img.getpixel((0, 0))[:3]

    # -- flood-fill：仅从「背景色簇」的种子点出发 --
    _flood_bg(img, bg_color)

    rgba = img.convert("RGBA")
    # -- 二次过滤：边缘/接近背景色像素强制 alpha=0 --
    rgba = _clean_edge_alpha(rgba, bg_color)

    # -- alpha 二值化：保留主体硬边缘，丢弃残留半透明像素 --
    r_ch, g_ch, b_ch, a_ch = rgba.split()
    a_ch = a_ch.point(lambda v: 255 if v > ALPHA_KEEP else 0)
    rgba = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))

    # -- 包围盒裁剪 --
    bbox = rgba.getbbox()
    if not bbox:
        raise ValueError("未检测到风扇主体：背景与主体对比不足")
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if bw < 40 or bh < 60:
        raise ValueError(
            f"识别出的主体过小（{bw}×{bh}），请换一张背景与风扇对比更明显的图")
    rgba = rgba.crop(bbox)
    fw, fh = rgba.size
    # 主体像素占比检查：避免「白主体被吃掉只剩边缘」导致残缺假象
    alpha = list(rgba.split()[3].getdata())
    keep_count = sum(1 for a in alpha if a > 0)
    keep_ratio = keep_count / (fw * fh) if fw * fh else 0
    if keep_ratio < 0.25:
        raise ValueError(
            f"识别出的主体残缺（仅 {keep_ratio:.0%} 像素），"
            "背景与主体颜色太接近，建议换背景对比明显的图")
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