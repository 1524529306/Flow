"""桌面风扇挂件：透明悬浮的迷你立式风扇，主交互入口。

控制中心（主窗口）退居兜底配置，日常操作直接在桌面上完成：

- 点击扇头 / 空格键：开关机
- 滚轮、点击底部档位圆点：切换 1~3 档
- 鼠标悬停 + ←/→ 方向键：手动摆头（每步 10°，范围 0~180°）
- 按住拖拽：移动挂件位置
- 右键：菜单（打开控制中心 / 自动摇头 / 退出）

视觉：v2.0.2 起改用 PIL 完整渲染（风扇 + 状态文字 + 档位圆点）。
透明度分平台实现：
  - Windows：Win32 ``UpdateLayeredWindow`` 真逐像素 alpha，根治 PNG
    皮肤边缘光晕（v2.0.x 的"阴影问题"）。
  - macOS：Aqua ``-transparent`` + ``systemTransparent``，PNG alpha
    直接合成（mac 本来就支持真透明）。
"""
from __future__ import annotations

import math
import sys
import time
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont, ImageTk

from ..controller import FanController, Snapshot
from ..protocol import ANGLE_CENTER, ANGLE_MAX, ANGLE_MIN, SPEED_MAX, SPEED_MIN
from . import skins
from .widget_art import HEAD_CX, HEAD_CY, HEAD_R, W, H, ModernFanArt

IS_MAC = sys.platform == "darwin"
UI_FONT = "PingFang SC" if IS_MAC else "Microsoft YaHei UI"

PIP_ON = "#56b6ba"
PIP_ON_EDGE = "#3fa3a8"
PIP_OFF_FILL = "#ffffff"
PIP_OFF_EDGE = "#d3dce2"
CHIP_BG = "#223442"

STATUS_Y = 262
PIP_Y = 284
PIP_XS = (90, 120, 150)

YAW_VISUAL = 35.0
ANGLE_STEP = 10
SPIN_SPEED = (0, 300, 520, 760)

# 真实风扇启停物理（v2.0.2）
SPIN_ACCEL = 2.2          # S 形加速基准（越大启动越快）
SPIN_COAST = 1.3          # 断电滑行摩擦系数（越大停得越快）
SPIN_STOP_EPS = 2.0       # 低于该转速（度/秒）视为完全停止
BOOT_JITTER_TIME = 0.5    # 启动颤振时长（秒）


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """跨平台加载中文字体。失败回退到 PIL 默认字体。"""
    if IS_MAC:
        paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/PingFang.ttc",
        ]
    else:
        paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


class FanWidget:
    """透明置顶的桌面风扇挂件。"""

    def __init__(self, root: tk.Tk, controller: FanController,
                 on_open_center: Callable[[], None],
                 on_quit: Callable[[], None]) -> None:
        self.root = root
        self.controller = controller
        self.on_open_center = on_open_center
        self.on_quit = on_quit

        # 动画状态
        self._spin = 0.0
        self._spin_vel = 0.0
        self._yaw = 0.0
        self._boot_jitter = 0.0       # 启动颤振剩余时长
        self._was_power = False       # 上一帧电源状态（检测开机沿）
        self._last_tick = time.monotonic()
        self._snap: Optional[Snapshot] = None

        # 拖拽状态
        self._press_xy: Optional[tuple] = None
        self._dragging = False

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)

        # Canvas 仅 macOS 分支用做 ImageTk 贴图；Windows 分支由 LayeredWindow
        # 完全接管绘制，Canvas 内容被覆盖但保留不报错。
        self.canvas = tk.Canvas(self.win, width=W, height=H,
                                highlightthickness=0, cursor="hand2")
        self.canvas.pack()

        # 视觉引擎
        self._skin_mgr = skins.SkinManager()
        self._skin_id = skins.load_skin_choice()
        self._art = self._skin_mgr.get_art(self._skin_id)
        self._font = _load_font(12)

        # 初始位置：屏幕右侧偏上
        sx = self.win.winfo_screenwidth()
        self.win.geometry(f"{W}x{H}+{max(0, sx - W - 60)}+140")

        self.win.update_idletasks()

        # 透明度：分平台实现
        if IS_MAC:
            self._photo = ImageTk.PhotoImage(self._art.compose(0, 0, False))
            self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
            try:
                self.win.attributes("-transparent", True)
                self.canvas.configure(bg="systemTransparent")
            except tk.TclError:
                self.canvas.configure(bg="#f2f5f7")
            self._layered = None
        else:
            self._photo = None
            from .winlayered import LayeredWindow
            self._layered = LayeredWindow(self.win.winfo_id(), W, H)

        self._bind_events()

        self._menu = tk.Menu(self.win, tearoff=0, font=(UI_FONT, 10))
        self._build_menu()
        self._tick()

    # ---------------------------------------------------------------- 菜单
    def _build_menu(self) -> None:
        self._menu.delete(0, "end")
        snap = self._snap
        self._menu.add_command(label="打开控制中心", command=self.on_open_center)
        osc_label = "自动摇头：关" if (snap and snap.oscillation) else "自动摇头：开"
        self._menu.add_command(
            label=osc_label,
            command=lambda: self.controller.set_oscillation(
                not (snap.oscillation if snap else False)))
        skin_menu = tk.Menu(self._menu, tearoff=0, font=(UI_FONT, 10))
        # v2.0.1：文字在前、勾选在后，用全角空格对齐
        for sid, name in self._skin_mgr.list_skins():
            mark = "✓" if sid == self._skin_id else "\u3000"
            skin_menu.add_command(label=f"{name}\u3000{mark}",
                                  command=lambda s=sid: self._set_skin(s))
        skin_menu.add_separator()
        skin_menu.add_command(label="上传新皮肤…", command=self._upload_skin)
        self._menu.add_cascade(label="皮肤", menu=skin_menu)
        self._menu.add_separator()
        self._menu.add_command(label="退出 FlowCC", command=self.on_quit)

    def _set_skin(self, skin_id: str) -> None:
        try:
            self._art = self._skin_mgr.get_art(skin_id)
        except Exception:
            self._art = ModernFanArt()
            skin_id = "classic"
        self._skin_id = skin_id
        skins.save_skin_choice(skin_id)

    def _upload_skin(self) -> None:
        path = filedialog.askopenfilename(
            title="选择风扇皮肤图片",
            filetypes=[("PNG 图片", "*.png"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            skin_id = self._skin_mgr.import_skin(path)
        except Exception:
            return
        self._set_skin(skin_id)

    # ---------------------------------------------------------------- 事件
    def _bind_events(self) -> None:
        # 统一绑定到 Toplevel 窗口，Windows 分支下 Canvas 被 layered 覆盖但
        # 仍能收事件；为安全起见直接绑到 win，两平台一致。
        target = self.win
        target.bind("<Button-1>", self._on_press)
        target.bind("<B1-Motion>", self._on_motion)
        target.bind("<ButtonRelease-1>", self._on_release)
        target.bind("<Button-3>", self._on_right_click)
        if IS_MAC:
            target.bind("<Button-2>", self._on_right_click)
        target.bind("<MouseWheel>", self._on_wheel)
        target.bind("<Enter>", lambda e: self.win.focus_set())
        target.bind("<Left>", lambda e: self._nudge_angle(-ANGLE_STEP))
        target.bind("<Right>", lambda e: self._nudge_angle(ANGLE_STEP))
        target.bind("<space>", lambda e: self._toggle_power())

    def _on_press(self, event) -> None:
        self._press_xy = (event.x_root, event.y_root,
                          self.win.winfo_x(), self.win.winfo_y())
        self._dragging = False

    def _on_motion(self, event) -> None:
        if not self._press_xy:
            return
        x0, y0, wx, wy = self._press_xy
        dx, dy = event.x_root - x0, event.y_root - y0
        if self._dragging or abs(dx) + abs(dy) > 4:
            self._dragging = True
            self.win.geometry(f"+{wx + dx}+{wy + dy}")

    def _on_release(self, event) -> None:
        if self._dragging:
            self._press_xy = None
            self._dragging = False
            return
        self._press_xy = None
        x, y = event.x, event.y
        # 档位圆点优先
        for level, px in zip(range(SPEED_MIN, SPEED_MAX + 1), PIP_XS):
            if (x - px) ** 2 + (y - PIP_Y) ** 2 <= 12 ** 2:
                self.controller.set_speed(level)
                return
        if self._in_head(x, y):
            self._toggle_power()

    def _on_right_click(self, _event) -> None:
        self._build_menu()
        try:
            self._menu.tk_popup(self.win.winfo_pointerx(), self.win.winfo_pointery())
        finally:
            self._menu.grab_release()

    def _on_wheel(self, event) -> None:
        snap = self._snap
        if not snap:
            return
        delta = 1 if event.delta > 0 else -1
        level = max(SPEED_MIN, min(SPEED_MAX, snap.speed + delta))
        self.controller.set_speed(level)

    def _toggle_power(self) -> None:
        snap = self._snap
        if snap and snap.connected:
            self.controller.set_power(not snap.power)

    def _nudge_angle(self, delta: int) -> None:
        snap = self._snap
        if snap and snap.connected:
            target = max(ANGLE_MIN, min(ANGLE_MAX, snap.angle + delta))
            self.controller.set_angle(target)

    @staticmethod
    def _in_head(x: int, y: int) -> bool:
        return (x - HEAD_CX) ** 2 + (y - HEAD_CY) ** 2 <= HEAD_R ** 2

    # ---------------------------------------------------------------- 动画
    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(0.1, now - self._last_tick)
        self._last_tick = now
        snap = self.controller.get_snapshot()
        self._snap = snap

        target_vel = SPIN_SPEED[snap.speed] if snap.power else 0

        # 开机沿 → 触发启动颤振（真实马达启动瞬间的小幅高频抖动）
        if snap.power and not self._was_power:
            self._boot_jitter = BOOT_JITTER_TIME
        self._was_power = snap.power

        if snap.power:
            # 启动/换档：S 形加速曲线（起步缓 → 中途快 → 接近目标收尾）
            ratio = min(1.0, self._spin_vel / max(1.0, target_vel))
            k = SPIN_ACCEL * (0.25 + 4.0 * ratio * (1.0 - ratio))
            self._spin_vel += (target_vel - self._spin_vel) * min(1.0, dt * k)
        else:
            # 断电滑行：摩擦指数减速，低于阈值完全停住（真实风扇惯性停转）
            self._spin_vel *= max(0.0, 1.0 - dt * SPIN_COAST)
            if self._spin_vel < SPIN_STOP_EPS:
                self._spin_vel = 0.0

        # 启动颤振：高频振荡叠加到角度，指数衰减
        jitter = 0.0
        if self._boot_jitter > 0.0:
            self._boot_jitter = max(0.0, self._boot_jitter - dt)
            decay = self._boot_jitter / BOOT_JITTER_TIME
            jitter = math.sin(now * 42.0) * 3.0 * decay

        self._spin = (self._spin + self._spin_vel * dt + jitter) % 360

        if snap.oscillation:
            target_yaw = YAW_VISUAL * math.sin(now * 0.9)
        else:
            target_yaw = (snap.angle - ANGLE_CENTER) / 90.0 * YAW_VISUAL
        self._yaw += (target_yaw - self._yaw) * min(1.0, dt * 6)

        frame = self._render(snap)
        if self._layered is not None:
            self._layered.update(frame)
        else:
            self._photo.paste(frame)
        self.win.after(40, self._tick)

    # ---------------------------------------------------------------- 渲染
    def _render(self, snap: Snapshot) -> Image.Image:
        """纯 PIL 渲染完整帧：风扇主体 + 状态文字 + 档位圆点。"""
        img = self._art.compose(self._spin, self._yaw, snap.power)
        self._draw_overlay(img, snap)
        return img

    def _draw_overlay(self, img: Image.Image, snap: Snapshot) -> None:
        """在风扇图上叠加状态文字底条和档位圆点（in-place）。"""
        d = ImageDraw.Draw(img)
        font = self._font

        # 状态文字
        if snap.power:
            status = f"{snap.speed} 档"
            if snap.oscillation:
                status += " · 摇头中"
            elif snap.angle != ANGLE_CENTER:
                status += f" · 朝向 {snap.angle}°"
        else:
            status = "已关机 · 点击扇头开启"
        bbox = d.textbbox((0, 0), status, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        cx, y = HEAD_CX, STATUS_Y
        pad_x, pad_y = 8, 3
        d.rounded_rectangle(
            [cx - tw // 2 - pad_x, y - th // 2 - pad_y,
             cx + tw // 2 + pad_x, y + th // 2 + pad_y],
            radius=4, fill=CHIP_BG)
        d.text((cx, y), status, fill="white", font=font, anchor="mm")

        # 档位圆点
        for level, px in zip(range(SPEED_MIN, SPEED_MAX + 1), PIP_XS):
            active = snap.power and level == snap.speed
            if active:
                fill, edge, fg = PIP_ON, PIP_ON_EDGE, "white"
            else:
                fill, edge, fg = PIP_OFF_FILL, PIP_OFF_EDGE, "#5b6673"
            d.ellipse([px - 10, PIP_Y - 10, px + 10, PIP_Y + 10],
                      fill=fill, outline=edge, width=1)
            d.text((px, PIP_Y), str(level), fill=fg, font=font, anchor="mm")