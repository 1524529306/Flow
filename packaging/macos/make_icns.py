#!/usr/bin/env python3
"""把 PNG 图标转成 macOS 用 .icns（纯 Python，跨平台可运行）。

用法：python make_icns.py <src.png> <dst.icns>
依赖：Pillow

.icns 格式：文件头 "icns"(4B) + 总长度(4B 大端)，后接若干图标块，
每块 = 类型标签(4B) + 长度(4B 大端，含 8 字节块头) + PNG 字节流。
macOS 可直接识别 PNG 编码的 icns 图块。
"""
import struct
import sys
from pathlib import Path

from PIL import Image

# 像素尺寸 -> icns 类型标签
SIZE_TO_TYPE = {
    16: "icp4",
    32: "icp5",
    64: "icp6",
    128: "ic07",
    256: "ic08",
    512: "ic09",
    1024: "ic10",
}


def _png_bytes(img: Image.Image) -> bytes:
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _chunk(typ: str, data: bytes) -> bytes:
    return struct.pack(">4sI", typ.encode("ascii"), len(data) + 8) + data


def main(src: str, dst: str) -> int:
    src_path = Path(src)
    if not src_path.exists():
        print(f"ERROR: 源图标不存在: {src_path}", file=sys.stderr)
        return 1

    icon = Image.open(src_path).convert("RGBA")
    print(f"源图标: {src_path} {icon.size}")

    chunks = []
    for size, typ in SIZE_TO_TYPE.items():
        resized = icon.resize((size, size), Image.LANCZOS)
        chunks.append(_chunk(typ, _png_bytes(resized)))
        print(f"  {typ} {size}x{size}")

    body = b"".join(chunks)
    icns = b"icns" + struct.pack(">I", len(body) + 8) + body

    out = Path(dst)
    out.write_bytes(icns)
    print(f"已生成: {out} ({len(icns)} bytes)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))