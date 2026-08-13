"""桌面挂件视觉渲染引擎 —— 经典渲染（3D 立体版，v2.0.1）。

用 PIL 离屏渲染分层素材（超采样抗锯齿），运行时只做轻量合成。
v2.0.1 起统一左上角光源，为外环 / 笼体 / 扇叶 / 轴心 / 底座 / 立柱
加入径向与线性渐变高光、阴影，替换 v2.0 的平面化观感。

渲染约定：
  - 主体形状一律先画「不透明」底色，再用半透明渐变层 alpha_composite
    叠出高光/阴影 —— 这样 RGB 被正确混合，alpha 仍保持 255，
    兼容末端的透明窗 alpha 二值化（不透明主体不产生粉边）。
  - 交互几何（HEAD_CX/HEAD_CY/HEAD_R、档位圆点）与旧版完全一致。
"""
from __future__ import annotations

import math
from PIL import Image, ImageDraw, ImageOps

W, H = 240, 300
HEAD_CX, HEAD_CY, HEAD_R = 120, 100, 64
SS = 3  # 超采样倍数

# 经典渲染调色板
RING_OUT = (246, 248, 249, 255)      # 外环主色
RING_EDGE = (214, 222, 227, 255)     # 外环描边
ACCENT = (70, 172, 178, 255)         # teal 环（开）
ACCENT_OFF = (176, 192, 200, 255)    # teal 环（关）
CAGE = (250, 251, 252, 255)          # 笼内底
GRILLE = (219, 225, 230, 255)        # 放射格栅
BLADE_ON = (66, 78, 92, 255)         # 扇叶（开）
BLADE_OFF = (186, 196, 205, 255)     # 扇叶（关）
HUB = (248, 250, 251, 255)           # 轴心
HUB_EDGE = (212, 220, 225, 255)      # 轴心描边
POLE = (235, 238, 241, 255)          # 立柱
POLE_SHADE = (205, 213, 219, 255)    # 立柱暗面
BASE_TOP = (246, 248, 250, 255)      # 底座顶面
BASE_SIDE = (211, 219, 224, 255)     # 底座侧面
SHADOW = (38, 50, 60, 60)            # 地面软阴影

# 高光 / 阴影强度
HIGHLIGHT = (255, 255, 255)
SHADE_RGB = (24, 40, 52)


def _down(img: Image.Image) -> Image.Image:
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


def _corner_light(size, small: int = 64) -> Image.Image:
    """左上角点光源的亮度 mask：左上=255 → 右下=0。"""
    w, h = size
    sm = Image.new("L", (small, small))
    px = sm.load()
    dmax = small * math.sqrt(2)
    for y in range(small):
        for x in range(small):
            d = math.hypot(x, y) / dmax
            px[x, y] = int(255 * (1.0 - d))
    return sm.resize((w, h), Image.BILINEAR)


def _light(base: Image.Image, mask: Image.Image, color, strength: int) -> Image.Image:
    """用 mask 控制透明度，把 color 叠加到 base 上（RGB 混合，alpha 不变）。"""
    overlay = Image.new("RGBA", base.size, (color[0], color[1], color[2], 0))
    a = mask.point(lambda v: int(v * strength / 255))
    overlay.putalpha(a)
    return Image.alpha_composite(base, overlay)


def _highlight(base: Image.Image, mask: Image.Image, strength: int) -> Image.Image:
    return _light(base, mask, HIGHLIGHT, strength)


def _shade(base: Image.Image, mask: Image.Image, strength: int) -> Image.Image:
    return _light(base, mask, SHADE_RGB, strength)


class ModernFanArt:
    """预渲染分层素材，运行时合成。"""

    def __init__(self) -> None:
        self.body = self._build_body()
        self.head_back_on = self._build_head_back(ACCENT)
        self.head_back_off = self._build_head_back(ACCENT_OFF)
        self.blades_on = self._build_blades(BLADE_ON)
        self.blades_off = self._build_blades(BLADE_OFF)
        self.hub = self._build_hub()
        self.head_w = self.head_back_on.width
        self.head_h = self.head_back_on.height

    # ------------------------------------------------------------- 机身
    def _build_body(self) -> Image.Image:
        img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx, s = HEAD_CX * SS, SS
        # 地面软阴影（左浅右深，随光源）
        d.ellipse([cx - 54 * s, 246 * s, cx + 54 * s, 264 * s], fill=SHADOW)
        # 底座侧面（暗） + 顶面（亮），叠出圆柱体厚度
        d.rounded_rectangle([cx - 46 * s, 232 * s, cx + 46 * s, 250 * s],
                            radius=9 * s, fill=BASE_SIDE)
        d.ellipse([cx - 46 * s, 226 * s, cx + 46 * s, 246 * s], fill=BASE_TOP)
        # 底座顶面：左上高光、右下阴影
        base_light = _corner_light((92 * s, 20 * s))
        base = Image.new("RGBA", (92 * s, 20 * s), BASE_TOP)
        base = _highlight(base, base_light, 46)
        base = _shade(base, ImageOps.invert(base_light), 30)
        img.alpha_composite(base, dest=(cx - 46 * s, 226 * s))
        # 立柱：左亮右暗 + 中央高光条
        d.rounded_rectangle([cx - 5 * s, 150 * s, cx + 5 * s, 234 * s],
                            radius=5 * s, fill=POLE)
        d.rounded_rectangle([cx + 1 * s, 152 * s, cx + 5 * s, 232 * s],
                            radius=4 * s, fill=POLE_SHADE)
        d.rectangle([cx - 2 * s, 156 * s, cx - 1 * s, 228 * s],
                    fill=(255, 255, 255, 200))  # 左缘高光条
        return _down(img)

    # ------------------------------------------------------------- 扇头背景
    def _build_head_back(self, accent) -> Image.Image:
        size = (HEAD_R + 10) * 2
        img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = size * SS // 2
        r_out = (HEAD_R + 6) * SS
        r_acc = (HEAD_R + 1) * SS
        r_cage = (HEAD_R - 2) * SS
        # 外环：描边 + 主色，叠对角高光/阴影 → 环体立体
        d.ellipse([c - r_out - SS, c - r_out - SS, c + r_out + SS, c + r_out + SS],
                  fill=RING_EDGE)
        d.ellipse([c - r_out, c - r_out, c + r_out, c + r_out], fill=RING_OUT)
        # 笼内底（略暗，体现凹陷）
        d.ellipse([c - r_acc, c - r_acc, c + r_acc, c + r_acc], fill=accent)
        d.ellipse([c - r_cage, c - r_cage, c + r_cage, c + r_cage], fill=CAGE)
        # 放射格栅（细辐条，置于扇叶之后）
        for i in range(28):
            ang = math.radians(i * 360 / 28)
            x0 = c + math.cos(ang) * 10 * SS
            y0 = c - math.sin(ang) * 10 * SS
            x1 = c + math.cos(ang) * (HEAD_R - 3) * SS
            y1 = c - math.sin(ang) * (HEAD_R - 3) * SS
            d.line([x0, y0, x1, y1], fill=GRILLE, width=max(1, SS // 2))
        # 整体对角光照：左上高光、右下阴影（在笼体与环上统一叠加）
        mask = _corner_light((size * SS, size * SS))
        img = _highlight(img, mask, 24)
        img = _shade(img, ImageOps.invert(mask), 26)
        return _down(img)

    # ------------------------------------------------------------- 扇叶
    def _build_blades(self, color) -> Image.Image:
        size = (HEAD_R + 10) * 2
        img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = size * SS // 2
        # 单片“逗号”形扇叶：大圆减去偏移圆，再裁到笼内
        blade = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
        bd = ImageDraw.Draw(blade)
        rb = int(0.52 * HEAD_R * SS)
        dist = int(0.50 * HEAD_R * SS)
        bx, by = c, c - dist
        bd.ellipse([bx - rb, by - rb, bx + rb, by + rb], fill=color)
        cut_r = int(rb * 0.92)
        cxo, cyo = bx + int(rb * 0.62), by - int(rb * 0.30)
        bd.ellipse([cxo - cut_r, cyo - cut_r, cxo + cut_r, cyo + cut_r],
                   fill=(0, 0, 0, 0))
        # 单片内做径向渐变（近轴心亮、叶尖暗）→ 立体
        blade_mask = _corner_light((size * SS, size * SS))
        # 只对叶片区域上色：用叶片 alpha 裁剪
        blade = _highlight(blade, blade_mask, 30)
        # 裁掉超出笼半径与轴心附近的部分
        mask_keep = Image.new("L", (size * SS, size * SS), 0)
        mk = ImageDraw.Draw(mask_keep)
        keep_r = int(0.90 * HEAD_R * SS)
        mk.ellipse([c - keep_r, c - keep_r, c + keep_r, c + keep_r], fill=255)
        mk.ellipse([c - 12 * SS, c - 12 * SS, c + 12 * SS, c + 12 * SS], fill=0)
        blade.putalpha(Image.composite(blade.split()[3],
                                       Image.new("L", blade.size, 0), mask_keep))
        for rot in (0, 120, 240):
            img.alpha_composite(blade.rotate(rot, resample=Image.BICUBIC))
        return _down(img)

    # ------------------------------------------------------------- 轴心
    def _build_hub(self) -> Image.Image:
        r = 13
        img = Image.new("RGBA", (r * 2 + 4, r * 2 + 4), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([1, 1, r * 2 + 2, r * 2 + 2], fill=HUB_EDGE)
        d.ellipse([2, 2, r * 2 + 1, r * 2 + 1], fill=HUB)
        # 球体高光：左上亮斑 + 右下弧影
        hub = Image.new("RGBA", (r * 2 + 4, r * 2 + 4), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hub)
        hd.ellipse([2, 2, r * 2 + 1, r * 2 + 1], fill=HUB)
        m = _corner_light((r * 2 + 4, r * 2 + 4), small=32)
        hub = _highlight(hub, m, 90)
        hub = _shade(hub, ImageOps.invert(m), 55)
        img = Image.alpha_composite(img, hub)
        return img

    # ------------------------------------------------------------- 合成
    def compose(self, spin_deg: float, yaw_deg: float, on: bool) -> Image.Image:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.alpha_composite(self.body)

        head = (self.head_back_on if on else self.head_back_off).copy()
        blades = (self.blades_on if on else self.blades_off)
        head.alpha_composite(blades.rotate(-spin_deg, resample=Image.BICUBIC))
        hw, hh = head.size
        hub = self.hub
        head.alpha_composite(hub, dest=((hw - hub.width) // 2, (hh - hub.height) // 2))

        k = math.cos(math.radians(yaw_deg))
        xoff = math.sin(math.radians(yaw_deg)) * 14
        if k < 0.995:
            new_w = max(24, int(hw * k))
            head = head.resize((new_w, hh), Image.LANCZOS)
            hw = new_w
        dest_x = HEAD_CX - hw // 2 + int(xoff)
        dest_y = HEAD_CY - hh // 2
        img.alpha_composite(head, dest=(dest_x, dest_y))

        # 透明窗(transparentcolor)只认纯色魔法色：半透明抗锯齿像素会留下
        # 粉边，故将 alpha 二值化，轮廓颜色保持正确。
        r, g, b, a = img.split()
        a = a.point(lambda v: 255 if v > 96 else 0)
        return Image.merge("RGBA", (r, g, b, a))
