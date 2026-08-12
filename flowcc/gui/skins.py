"""皮肤系统：经典渲染 + 内置四风格 + 第三方上传自动适配。

内置皮肤源图位于 assets/skins/（打包时随 exe 携带）；处理缓存与
自定义皮肤位于 %APPDATA%/FlowCC/skins/。选择结果存入配置 "skin"。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from . import skin_processor
from .widget_art import W, H, ModernFanArt

CLASSIC = ("classic", "经典渲染")
BUILTIN = [
    ("style_a", "现代简约", "style_A_modern.png"),
    ("style_b", "深色霓虹", "style_B_glass.png"),
    ("style_c", "奶油可爱", "style_C_cream.png"),
    ("style_d", "机甲科技", "style_D_mecha.png"),
]
DEFAULT_SKIN = "style_a"
FAN_AREA_BOTTOM = 252  # 风扇图放置区底边（状态条之上）


def _builtin_dir() -> Path | None:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "assets" / "skins")
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / "skins")
    for cand in candidates:
        if cand.exists():
            return cand
    return None


def user_skin_dir() -> Path:
    from ..config import app_data_dir
    folder = app_data_dir() / "skins"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def load_skin_choice() -> str:
    from ..config import load_config
    return load_config().get("skin", DEFAULT_SKIN)


def save_skin_choice(skin_id: str) -> None:
    from ..config import load_config, save_config
    data = load_config()
    data["skin"] = skin_id
    save_config(data)


class ImageSkinArt:
    """图片皮肤渲染器：静态主体 + 旋转叶影叠加。"""

    def __init__(self, meta: dict) -> None:
        full = Image.open(meta["png"]).convert("RGBA")
        fw, fh = full.size
        scale = min((W - 16) / fw, (FAN_AREA_BOTTOM - 6) / fh)
        sw, sh = max(8, int(fw * scale)), max(8, int(fh * scale))
        full = full.resize((sw, sh), Image.LANCZOS)
        # 抗锯齿半透明边缘在透明窗上会留粉边：alpha 二值化
        r, g, b, a = full.split()
        a = a.point(lambda v: 255 if v > 96 else 0)
        self.img = Image.merge("RGBA", (r, g, b, a))
        hx, hy, hr = meta["head"]
        self.head = (hx * scale, hy * scale, hr * scale)
        self._swirl = self._build_swirl(self.head[2])

    @staticmethod
    def _build_swirl(r: float) -> Image.Image:
        size = max(24, int(r * 2.4))
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        c = size / 2
        for i in range(3):  # 三片半透明叶影，旋转后叠加在扇头区
            ang = math.radians(i * 120)
            ex = c + math.cos(ang) * r * 0.5
            ey = c + math.sin(ang) * r * 0.5
            d.ellipse([ex - r * 0.55, ey - r * 0.30, ex + r * 0.55, ey + r * 0.30],
                      fill=(40, 52, 64, 88))
        d.ellipse([c - r * 0.16, c - r * 0.16, c + r * 0.16, c + r * 0.16],
                  fill=(255, 255, 255, 110))
        return layer

    def compose(self, spin_deg: float, yaw_deg: float, on: bool) -> Image.Image:
        img = self.img
        k = math.cos(math.radians(yaw_deg))
        xoff = math.sin(math.radians(yaw_deg)) * 10
        if k < 0.995:
            img = img.resize((max(16, int(img.width * k)), img.height),
                             Image.LANCZOS)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dx = (W - img.width) // 2 + int(xoff)
        dy = FAN_AREA_BOTTOM - img.height
        canvas.alpha_composite(img, dest=(dx, dy))
        if on:
            swirl = self._swirl.rotate(-spin_deg, resample=Image.BICUBIC)
            hx, hy = self.head[0], self.head[1]
            px = dx + int(hx * k) - swirl.width // 2
            py = dy + int(hy) - swirl.height // 2
            canvas.alpha_composite(swirl, dest=(px, py))
        return canvas


class SkinManager:
    """皮肤清单 / 处理缓存 / 导入。"""

    def __init__(self) -> None:
        self._cache: dict[str, object] = {}

    def list_skins(self) -> list[tuple[str, str]]:
        skins = [CLASSIC]
        bdir = _builtin_dir()
        if bdir:
            for sid, name, fname in BUILTIN:
                if (bdir / fname).exists():
                    skins.append((sid, name))
        for meta_file in sorted(user_skin_dir().glob("custom_*.json")):
            skins.append((meta_file.stem, meta_file.stem.replace("custom_", "自定义·")))
        return skins

    def get_art(self, skin_id: str):
        if skin_id in self._cache:
            return self._cache[skin_id]
        art = self._build(skin_id)
        self._cache[skin_id] = art
        return art

    def _meta_path(self, skin_id: str) -> Path:
        return user_skin_dir() / f"{skin_id}.json"

    def _build(self, skin_id: str):
        if skin_id == CLASSIC[0]:
            return ModernFanArt()
        meta_path = self._meta_path(skin_id)
        if not meta_path.exists():
            src = self._source_of(skin_id)
            if src is None:
                return ModernFanArt()
            skin_processor.process_skin(src, user_skin_dir() / f"{skin_id}.png",
                                        meta_path)
        return ImageSkinArt(json.loads(meta_path.read_text(encoding="utf-8")))

    @staticmethod
    def _source_of(skin_id: str) -> Path | None:
        bdir = _builtin_dir()
        if bdir:
            for sid, _name, fname in BUILTIN:
                if sid == skin_id:
                    return bdir / fname
        return None

    def import_skin(self, src_path) -> str:
        """上传第三方皮肤：处理适配并登记，返回皮肤 id。"""
        stem = Path(src_path).stem
        skin_id = f"custom_{stem}"[:60]
        skin_processor.process_skin(
            src_path, user_skin_dir() / f"{skin_id}.png", self._meta_path(skin_id))
        self._cache.pop(skin_id, None)
        return skin_id
