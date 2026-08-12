"""皮肤自动适配引擎测试：合成风扇图验证去背景与扇头定位。"""
import os
import tempfile
import unittest

from PIL import Image, ImageDraw

from flowcc.gui import skin_processor


class TestSkinProcessor(unittest.TestCase):
    @staticmethod
    def _synthetic_fan() -> Image.Image:
        img = Image.new("RGB", (400, 500), (245, 246, 248))
        d = ImageDraw.Draw(img)
        d.ellipse([100, 60, 300, 260], fill=(80, 180, 185))     # 外环
        d.ellipse([120, 80, 280, 240], fill=(250, 250, 250))    # 笼体
        d.rectangle([190, 260, 210, 400], fill=(238, 238, 238))  # 立柱
        d.ellipse([120, 396, 280, 436], fill=(228, 228, 228))    # 底座
        return img

    def test_process_detects_head(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src.png")
            self._synthetic_fan().save(src)
            meta = skin_processor.process_skin(
                src, os.path.join(td, "out.png"), os.path.join(td, "out.json"))
            self.assertTrue(os.path.exists(meta["png"]))
        cx, cy, r = meta["head"]
        fw, fh = meta["size"]
        # 裁剪后主体宽 200（x:100~300），扇头半径应接近 100、圆心居中偏上
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


if __name__ == "__main__":
    unittest.main()
