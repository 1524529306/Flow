"""桌面挂件视觉渲染引擎 —— 风格 A「现代简约」。

用 PIL 离屏渲染分层素材（超采样抗锯齿），运行时只做轻量合成：
    机身层（阴影/底座/立柱） + 扇头层（外环/格栅/扇叶/轴心）
扇叶旋转用预渲染图层 rotate，摆头用水平缩放 + 偏移模拟偏转。
交互几何（HEAD_CX/HEAD_CY/HEAD_R、档位圆点坐标）与旧版完全一致。
"""
from __future__ import annotations

import math
from PIL import Image, ImageDraw

W, H = 240, 300
HEAD_CX, HEAD_CY, HEAD_R = 120, 100, 64
SS = 3  # 超采样倍数

# 风格 A 调色板（取自样图）
RING_OUT = (244, 246, 247, 255)
RING_EDGE = (228, 233, 236, 255)
ACCENT = (86, 182, 186, 255)
ACCENT_OFF = (203, 213, 220, 255)
CAGE = (251, 252, 253, 255)
GRILLE = (233, 237, 240, 255)
BLADE_ON = (74, 84, 98, 255)
BLADE_OFF = (198, 207, 215, 255)
HUB = (250, 251, 252, 255)
HUB_EDGE = (226, 231, 235, 255)
POLE = (240, 242, 244, 255)
POLE_SHADE = (222, 227, 231, 255)
BASE_TOP = (247, 249, 250, 255)
BASE_SIDE = (228, 233, 236, 255)
SHADOW = (40, 52, 62, 64)


def _down(img: Image.Image) -> Image.Image:
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


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
        # 地面软阴影
        d.ellipse([cx - 52 * s, 246 * s, cx + 52 * s, 262 * s], fill=SHADOW)
        # 底座（上亮侧暗的两层椭圆，模拟厚度）
        d.rounded_rectangle([cx - 46 * s, 232 * s, cx + 46 * s, 250 * s],
                            radius=9 * s, fill=BASE_SIDE)
        d.ellipse([cx - 46 * s, 226 * s, cx + 46 * s, 246 * s], fill=BASE_TOP)
        # 立柱（左亮右暗）
        d.rounded_rectangle([cx - 5 * s, 150 * s, cx + 5 * s, 234 * s],
                            radius=5 * s, fill=POLE)
        d.rounded_rectangle([cx + 1 * s, 152 * s, cx + 5 * s, 232 * s],
                            radius=4 * s, fill=POLE_SHADE)
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
        # 白色外环（带极浅外描边）
        d.ellipse([c - r_out - SS, c - r_out - SS, c + r_out + SS, c + r_out + SS],
                  fill=RING_EDGE)
        d.ellipse([c - r_out, c - r_out, c + r_out, c + r_out], fill=RING_OUT)
        # teal 细环
        d.ellipse([c - r_acc, c - r_acc, c + r_acc, c + r_acc], fill=accent)
        # 笼内白底
        d.ellipse([c - r_cage, c - r_cage, c + r_cage, c + r_cage], fill=CAGE)
        # 放射格栅（细辐条，置于扇叶之后）
        for i in range(28):
            ang = math.radians(i * 360 / 28)
            x0 = c + math.cos(ang) * 10 * SS
            y0 = c - math.sin(ang) * 10 * SS
            x1 = c + math.cos(ang) * (HEAD_R - 3) * SS
            y1 = c - math.sin(ang) * (HEAD_R - 3) * SS
            d.line([x0, y0, x1, y1], fill=GRILLE, width=max(1, SS // 2))
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
        rb = int(0.52 * HEAD_R * SS)          # 叶盘半径
        dist = int(0.50 * HEAD_R * SS)        # 叶盘中心到轴心距离
        bx, by = c, c - dist                  # 朝上
        bd.ellipse([bx - rb, by - rb, bx + rb, by + rb], fill=color)
        # 偏移切圆 → 逗号/镰刀形
        cut_r = int(rb * 0.92)
        cxo, cyo = bx + int(rb * 0.62), by - int(rb * 0.30)
        bd.ellipse([cxo - cut_r, cyo - cut_r, cxo + cut_r, cyo + cut_r],
                   fill=(0, 0, 0, 0))
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
        # 顶部高光
        d.ellipse([r * 0.7, r * 0.55, r * 1.5, r * 1.2], fill=(255, 255, 255, 200))
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
