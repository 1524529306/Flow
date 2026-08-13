"""Windows 真透明窗（per-pixel alpha）：UpdateLayeredWindow 封装。

tkinter 的 ``-transparentcolor`` 只支持单一"魔法色"透明，PNG 皮肤的
半透明抗锯齿边缘会留下杂色光晕（用户看到的"阴影"）。改用 Win32
layered window 逐像素合成 RGBA，彻底消除边缘光晕。

用法：
    lw = LayeredWindow(hwnd, width, height)
    lw.update(rgba_image)   # 传入 PIL RGBA Image，立即重绘
    lw.close()              # 释放 GDI 资源

注意：
  - 调用 UpdateLayeredWindow 后，窗口由传入位图完全接管绘制，
    不再显示任何 tkinter 子控件（Canvas/文字等）。
  - 因此调用方须用 PIL 渲染完整帧（含文字、圆点等所有视觉）。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
BI_RGB = 0


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),   # 负值 = top-down（内存首行在顶部）
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class _POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


# ---- 显式函数签名，避免 64 位指针/返回值被截断 ----
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(_POINT), ctypes.POINTER(_SIZE),
    wintypes.HDC, ctypes.POINTER(_POINT), wintypes.COLORREF,
    ctypes.POINTER(_BLENDFUNCTION), wintypes.DWORD,
]
user32.UpdateLayeredWindow.restype = wintypes.BOOL

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.argtypes = [
    wintypes.HDC, ctypes.POINTER(_BITMAPINFO), wintypes.UINT,
    ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL


class LayeredWindow:
    """把 RGBA 位图逐像素合成到指定 HWND（真透明、无边缘光晕）。"""

    def __init__(self, hwnd: int, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._hwnd = hwnd
        self._hbmp = 0
        self._hdc = 0

        # 给窗口加 WS_EX_LAYERED 扩展样式
        exstyle = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, exstyle | WS_EX_LAYERED)

        # 创建 32bpp top-down DIB section，拿到可直接写像素的地址
        self._hdc = gdi32.CreateCompatibleDC(0)
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height            # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bmi.bmiHeader.biSizeImage = width * height * 4
        self._pbits = ctypes.c_void_p()
        self._hbmp = gdi32.CreateDIBSection(
            self._hdc, ctypes.byref(bmi), 0, ctypes.byref(self._pbits), None, 0)
        gdi32.SelectObject(self._hdc, self._hbmp)

        self._blend = _BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        self._size = _SIZE(width, height)
        self._pt_src = _POINT(0, 0)

    def update(self, img: Image.Image) -> None:
        """把 RGBA 图写入 DIB 并刷新窗口。img 尺寸须与构造时一致。"""
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height), Image.LANCZOS)
        # RGBA → BGRA 字节序（DIB 32bpp 为 BGRX，含 alpha 用于预乘合成）
        r, g, b, a = img.convert("RGBA").split()
        bgra = Image.merge("RGBA", (b, g, r, a))
        raw = bgra.tobytes()
        ctypes.memmove(self._pbits, raw, len(raw))
        user32.UpdateLayeredWindow(
            self._hwnd, None, None, ctypes.byref(self._size),
            self._hdc, ctypes.byref(self._pt_src), 0,
            ctypes.byref(self._blend), ULW_ALPHA)

    def close(self) -> None:
        if self._hbmp:
            gdi32.DeleteObject(self._hbmp)
            self._hbmp = 0
        if self._hdc:
            gdi32.DeleteDC(self._hdc)
            self._hdc = 0
