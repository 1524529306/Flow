"""皮肤 PNG 严格校验器测试（v2.0.0 设计）。

校验行为：
  - RGBA 含透明通道：通过
  - RGB 不透明：拒绝（必须导出时勾选透明背景）
  - RGBA 但几乎全透明：拒绝（主体不可识别）
"""
import os
import tempfile
import unittest

from PIL import Image, ImageDraw

from flowcc.gui import skin_processor


class TestSkinProcessorStrict(unittest.TestCase):
    @staticmethod
    def _synthetic_fan_transparent() -> Image.Image:
        """合成一张 RGBA 含透明背景的风扇图。"""
        img = Image.new("RGBA", (400, 500), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([100, 60, 300, 260], fill=(80, 180, 185, 255))   # 外环
        d.ellipse([120, 80, 280, 240], fill=(250, 250, 250, 255))  # 笼体
        d.rectangle([190, 260, 210, 400], fill=(238, 238, 238, 255))  # 立柱
        d.ellipse([120, 396, 280, 436], fill=(228, 228, 228, 255))    # 底座
        return img

    @staticmethod
    def _synthetic_fan_opaque() -> Image.Image:
        """合成一张 RGB 不透明的整图（v2.0 必须拒绝）。"""
        img = Image.new("RGB", (400, 500), (245, 246, 248))
        d = ImageDraw.Draw(img)
        d.ellipse([100, 60, 300, 260], fill=(80, 180, 185))
        d.ellipse([120, 80, 280, 240], fill=(250, 250, 250))
        d.rectangle([190, 260, 210, 400], fill=(238, 238, 238))
        d.ellipse([120, 396, 280, 436], fill=(228, 228, 228))
        return img

    @staticmethod
    def _process(img: Image.Image):
        """返回 (meta, tempdir)。调用方负责清理。"""
        td = tempfile.mkdtemp()
        src = os.path.join(td, "src.png")
        img.save(src)
        meta = skin_processor.process_skin(
            src, os.path.join(td, "out.png"), os.path.join(td, "out.json"))
        return meta, td

    def test_transparent_png_passes(self):
        """RGBA 含透明背景：通过。"""
        meta, td = self._process(self._synthetic_fan_transparent())
        try:
            cx, cy, r = meta["head"]
            fw, fh = meta["size"]
            self.assertAlmostEqual(cx, fw / 2, delta=12)
            self.assertAlmostEqual(r, 100, delta=12)
            self.assertLess(cy, fh * 0.6)
            # 输出文件存在
            self.assertTrue(os.path.exists(meta["png"]))
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)

    def test_opaque_png_rejected(self):
        """RGB 不透明 PNG：必须拒绝并指向文档。"""
        with self.assertRaises(skin_processor.SkinFormatError) as ctx:
            self._process(self._synthetic_fan_opaque())
        msg = str(ctx.exception)
        self.assertIn("RGBA", msg)
        self.assertIn("透明", msg)
        self.assertIn("SKIN_GUIDE.md", msg)

    def test_nearly_blank_rejected(self):
        """RGBA 但几乎全透明：拒绝（找不到主体）。"""
        img = Image.new("RGBA", (400, 500), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.point((200, 250), fill=(255, 0, 0, 255))
        with self.assertRaises(skin_processor.SkinFormatError):
            meta, td = self._process(img)
            import shutil
            shutil.rmtree(td, ignore_errors=True)

    def test_small_subject_rejected(self):
        """主体太小：拒绝。"""
        img = Image.new("RGBA", (400, 500), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([195, 245, 205, 255], fill=(80, 180, 185, 255))  # 10x10 圆
        with self.assertRaises(skin_processor.SkinFormatError) as ctx:
            meta, td = self._process(img)
            import shutil
            shutil.rmtree(td, ignore_errors=True)
        self.assertIn("主体尺寸过小", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()