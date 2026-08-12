"""皮肤自动适配引擎测试：合成风扇图验证去背景与扇头定位。

覆盖：
1. 单色背景（回归）
2. 渐变天空背景（粉紫→橙黄）：v1.4.1 引入
3. 双色调背景（绿+紫分块）：v1.4.1 引入
4. 空白图被拒绝
"""
import os
import tempfile
import unittest

from PIL import Image, ImageDraw

from flowcc.gui import skin_processor


class TestSkinProcessor(unittest.TestCase):
    @staticmethod
    def _fan_draw(d, x0, y0, w, h):
        """在画布 d 上画一个标准风扇（青色环 + 白白色机身 + 立柱 + 底座）。"""
        d.ellipse([x0, y0, x0 + w, y0 + h], fill=(80, 180, 185))            # 外环
        d.ellipse([x0 + 20, y0 + 20, x0 + w - 20, y0 + h - 20],
                  fill=(250, 250, 250))                                       # 笼体
        cx, cy = x0 + w // 2, y0 + h // 2
        d.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], fill=(74, 84, 98))    # 轴心
        d.rectangle([cx - 10, y0 + h, cx + 10, y0 + h + 140],
                    fill=(238, 238, 238))                                    # 立柱
        d.ellipse([x0 + 20, y0 + h + 136, x0 + w - 20, y0 + h + 176],
                  fill=(228, 228, 228))                                      # 底座

    @staticmethod
    def _synthetic_fan() -> Image.Image:
        img = Image.new("RGB", (400, 500), (245, 246, 248))
        d = ImageDraw.Draw(img)
        d.ellipse([100, 60, 300, 260], fill=(80, 180, 185))
        d.ellipse([120, 80, 280, 240], fill=(250, 250, 250))
        d.rectangle([190, 260, 210, 400], fill=(238, 238, 238))
        d.ellipse([120, 396, 280, 436], fill=(228, 228, 228))
        return img

    @staticmethod
    def _synthetic_gradient_bg() -> Image.Image:
        """粉紫→橙黄渐变天空背景，模拟用户截图场景。"""
        img = Image.new("RGB", (400, 500))
        for y in range(500):
            t = y / 499
            r = int(180 * (1 - t) + 240 * t)
            g = int(120 * (1 - t) + 200 * t)
            b = int(200 * (1 - t) + 100 * t)
            for x in range(400):
                img.putpixel((x, y), (r, g, b))
        d = ImageDraw.Draw(img)
        d.ellipse([100, 60, 300, 260], fill=(80, 180, 185))
        d.ellipse([120, 80, 280, 240], fill=(250, 250, 250))
        d.ellipse([180, 150, 220, 190], fill=(74, 84, 98))
        d.rectangle([190, 260, 210, 400], fill=(238, 238, 238))
        d.ellipse([120, 396, 280, 436], fill=(228, 228, 228))
        return img

    @staticmethod
    def _synthetic_duotone_bg() -> Image.Image:
        """左绿右紫分块背景：测试多点采样聚类。"""
        img = Image.new("RGB", (400, 500), (40, 200, 80))
        d = ImageDraw.Draw(img)
        d.rectangle([280, 0, 400, 500], fill=(180, 50, 200))
        d.ellipse([100, 60, 300, 260], fill=(80, 180, 185))
        d.ellipse([120, 80, 280, 240], fill=(250, 250, 250))
        d.rectangle([190, 260, 210, 400], fill=(238, 238, 238))
        d.ellipse([120, 396, 280, 436], fill=(228, 228, 228))
        return img

    def _process(self, src_img: Image.Image) -> tuple[dict, Image.Image]:
        """跑一次 process_skin，返回 (meta, 输出 RGBA 图)。"""
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src.png")
            out_png = os.path.join(td, "out.png")
            out_meta = os.path.join(td, "out.json")
            src_img.save(src)
            meta = skin_processor.process_skin(src, out_png, out_meta)
            return meta, Image.open(out_png).convert("RGBA")

    def _alpha_hist(self, img: Image.Image) -> tuple[int, int, int]:
        """返回 (透明, 半透明, 不透明) 像素计数。"""
        hist = img.split()[3].histogram()
        return hist[0], sum(hist[1:255]), hist[255]

    def test_process_detects_head(self):
        meta, _ = self._process(self._synthetic_fan())
        cx, cy, r = meta["head"]
        fw, fh = meta["size"]
        self.assertAlmostEqual(cx, fw / 2, delta=12)
        self.assertAlmostEqual(r, 100, delta=12)
        self.assertLess(cy, fh * 0.6)

    def test_process_rejects_blank(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "blank.png")
            Image.new("RGB", (200, 200), (245, 246, 248)).save(src)
            with self.assertRaises(ValueError):
                skin_processor.process_skin(
                    src, os.path.join(td, "o.png"), os.path.join(td, "o.json"))

    def test_process_strips_gradient_bg(self):
        """v1.4.1 修复：渐变天空背景应被完全去干净，无半透明残留。"""
        _, out = self._process(self._synthetic_gradient_bg())
        zero, mid, full = self._alpha_hist(out)
        total = zero + mid + full
        # 渐变背景应被彻底剥离：alpha=0 应占大部分
        self.assertGreater(zero / total, 0.40)
        # 关键断言：无半透明残留像素（粉边的元凶）
        self.assertEqual(mid, 0,
                         f"渐变背景存在 {mid} 个半透明残留像素，应为 0")
        # 主体（不透明像素）应保留
        self.assertGreater(full, 1000)

    def test_process_handles_duotone_bg(self):
        """v1.4.1 修复：双色调背景应被去干净。"""
        _, out = self._process(self._synthetic_duotone_bg())
        zero, mid, full = self._alpha_hist(out)
        total = zero + mid + full
        # 双色调：背景占主体外围，flood-fill 能吃掉大部分但留下"被主体围住的湖"
        self.assertGreater(zero / total, 0.30)
        # 关键：无半透明残留像素（粉边的元凶）
        self.assertEqual(mid, 0)
        # 主体（不透明像素）应保留
        self.assertGreater(full, 1000)

    def test_process_keeps_white_subject_on_near_bg(self):
        """v1.4.1：白主体+近色背景应保留主体（不被误吃）。"""
        img = Image.new("RGB", (400, 500), (252, 252, 252))
        d = ImageDraw.Draw(img)
        d.ellipse([100, 60, 300, 260], fill=(80, 180, 185))
        d.ellipse([120, 80, 280, 240], fill=(255, 255, 255))
        d.rectangle([190, 260, 210, 400], fill=(238, 238, 238))
        d.ellipse([120, 396, 280, 436], fill=(228, 228, 228))
        meta, out = self._process(img)
        zero, mid, full = self._alpha_hist(out)
        total = zero + mid + full
        # 关键：算法不抛错（白主体被保留），主体占比合理
        self.assertGreater(full / total, 0.40,
                           f"白主体应被保留，实际仅 {full / total:.0%}")
        # 主体识别框应包含扇头区域
        cx, _, r = meta["head"]
        fw, _ = meta["size"]
        self.assertAlmostEqual(cx, fw / 2, delta=20)


if __name__ == "__main__":
    unittest.main()
