"""离线皮肤生成器：把 _sources/ 下的不透明 PNG 批量处理成透明 PNG。

v2.0.0 起，所有内置皮肤 PNG 必须在**设计时**生成透明背景，
运行时只做校验与缩放，不再做去背景处理。

策略：
  1. 优先使用 rembg（ML 模型，u2net 176MB），效果最好。
     首次运行会下载模型到 ``%USERPROFILE%/.u2net/``。
  2. 失败回退到 PIL flood-fill（无额外依赖，效果较差）。

用法：
    python -m tools.build_skins                  # 处理全部 _sources/*.png
    python -m tools.build_skins path/to/img.png  # 处理单张
    python -m tools.build_skins --check          # 只检查源图不实际处理

输出：覆盖到 ``assets/skins/<原文件名>``（已是 RGBA 透明 PNG）。
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PIL import Image, ImageDraw

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("build_skins")

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "assets" / "skins" / "_sources"
OUTPUT_DIR = ROOT / "assets" / "skins"


def remove_bg_rembg(src: Image.Image) -> Image.Image:
    """用 rembg (u2net) 移除背景，结果已是 RGBA。"""
    from rembg import remove
    log.info("使用 rembg (u2net) 处理...")
    return remove(src).convert("RGBA")


def remove_bg_pil_floodfill(src: Image.Image) -> Image.Image:
    """PIL 兜底：四角色采样聚类识别背景色，从四角 flood-fill。

    对简单纯色背景效果尚可；渐变 / 复杂背景效果不佳，建议换 rembg。
    """
    log.warning("rembg 不可用，使用 PIL flood-fill 兜底（效果有限）")
    img = src.convert("RGBA")
    w, h = img.size

    # 四角采样
    corners = [img.getpixel((0, 0)), img.getpixel((w - 1, 0)),
               img.getpixel((0, h - 1)), img.getpixel((w - 1, h - 1))]
    avg = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
    log.info("识别到背景色 RGB=%s", avg)

    # 用 flood-fill 替换背景为透明（thresh=80 较宽松）
    fill = (255, 0, 255, 0)  # 标记用，flood-fill 后会替换
    ImageDraw.floodfill(img, (0, 0), fill, thresh=80)
    ImageDraw.floodfill(img, (w - 1, 0), fill, thresh=80)
    ImageDraw.floodfill(img, (0, h - 1), fill, thresh=80)
    ImageDraw.floodfill(img, (w - 1, h - 1), fill, thresh=80)

    # 把标记色替换为透明
    px = img.load()
    count = 0
    for y in range(h):
        for x in range(w):
            if px[x, y][:3] == fill[:3]:
                px[x, y] = (0, 0, 0, 0)
                count += 1
    log.info("flood-fill 清掉 %d 个背景像素", count)
    return img


def remove_background(src: Image.Image) -> Image.Image:
    """优先 rembg，失败回退 PIL。"""
    try:
        return remove_bg_rembg(src)
    except Exception as exc:
        log.error("rembg 失败: %s", exc)
        return remove_bg_pil_floodfill(src)


def process_one(src_path: Path, out_path: Path) -> None:
    """处理单张源 PNG。"""
    log.info("处理 %s -> %s", src_path.name, out_path.name)
    src = Image.open(src_path)
    src.load()
    if src.mode != "RGB":
        log.warning("源图 mode=%s，建议源图为 RGB 不透明", src.mode)
    result = remove_background(src)
    # 二次过滤：rembg 在阴影 / 渐变 / 弱纹理边缘会留下半透明残影
    # （alpha 50-150），合成时显示为深色污点。把弱像素一律清掉：
    # - alpha < 200 → 0（rembg 不确定就是背景）
    # - 其余 → 255（主体边缘）
    r, g, b, a = result.split()
    a = a.point(lambda v: 255 if v >= 200 else 0)
    result = Image.merge("RGBA", (r, g, b, a))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(out_path, format="PNG", optimize=True)
    log.info("  -> %s (%dx%d, %d KB)",
             out_path.name, result.size[0], result.size[1],
             out_path.stat().st_size // 1024)


def main() -> int:
    ap = argparse.ArgumentParser(description="FlowCC 内置皮肤批量生成器")
    ap.add_argument("inputs", nargs="*",
                    help="输入 PNG 路径；省略则处理 _sources/ 下全部")
    ap.add_argument("--check", action="store_true",
                    help="只检查源图不实际处理（依赖检查）")
    args = ap.parse_args()

    if args.check:
        try:
            import rembg  # noqa: F401
            log.info("rembg 已安装 ✓")
        except ImportError:
            log.warning("rembg 未安装，将使用 PIL flood-fill 兜底")
        return 0

    targets: list[Path] = []
    if args.inputs:
        for inp in args.inputs:
            targets.append(Path(inp).resolve())
    else:
        if not SOURCE_DIR.exists():
            log.error("源目录不存在: %s", SOURCE_DIR)
            return 1
        targets = sorted(SOURCE_DIR.glob("*.png"))
        if not targets:
            log.error("源目录 %s 下无 PNG 文件", SOURCE_DIR)
            return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for src in targets:
        if not src.exists():
            log.error("文件不存在: %s", src)
            return 1
        out = OUTPUT_DIR / src.name
        process_one(src, out)

    log.info("完成。共处理 %d 张皮肤到 %s", len(targets), OUTPUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())