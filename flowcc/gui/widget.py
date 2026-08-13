"""桌面风扇挂件：透明悬浮的迷你立式风扇，主交互入口。

控制中心（主窗口）退居兜底配置，日常操作直接在桌面上完成：

- 点击扇头 / 空格键：开关机
- 滚轮、点击底部档位圆点：切换 1~3 档
- 鼠标悬停 + ←/→ 方向键：手动摆头（每步 10°，范围 0~180°）
- 按住拖拽：移动挂件位置
- 右键：菜单（打开控制中心 / 自动摇头 / 退出）

视觉（v1.2 风格 A 现代简约）：由 widget_art.ModernFanArt 用 PIL 分层渲染，
扇叶按档位转速旋转（带停机惯性），摆头时扇头平滑偏转。
"""
from __future__ import annotations

import math
import sys
import time
import tkinter as tk
from tkinter import filedialog
from typing import Callable, Optional

from PIL import ImageTk

from ..controller import FanController, Snapshot
from ..protocol import ANGLE_CENTER, ANGLE_MAX, ANGLE_MIN, SPEED_MAX, SPEED_MIN
from . import skins
from .widget_art import HEAD_CX, HEAD_CY, HEAD_R, W, H, ModernFanArt

IS_MAC = sys.platform == "darwin"
UI_FONT = "PingFang SC" if IS_MAC else "Microsoft YaHei UI"

# 透明窗的“魔法色”：画布背景用该色，再声明为透明，即得异形悬浮窗（Windows）。
MAGIC = "#ff00ff"

STATUS_Y = 262
PIP_Y = 284
PIP_XS = (90, 120, 150)

YAW_VISUAL = 35.0          # 摆头在视觉上的最大偏转角（度）
ANGLE_STEP = 10            # 方向键每步摆头角度
SPIN_SPEED = (0, 300, 520, 760)   # 各档位扇叶视觉转速（度/秒）

PIP_ON = "#56b6ba"
PIP_ON_EDGE = "#3fa3a8"
PIP_OFF_FILL = "#ffffff"
PIP_OFF_EDGE = "#d3dce2"
CHIP_BG = "#223442"


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
        self._spin = 0.0          # 扇叶当前角度
        self._spin_vel = 0.0      # 当前视觉转速（带惯性）
        self._yaw = 0.0           # 扇头视觉偏转角
        self._last_tick = time.monotonic()
        self._snap: Optional[Snapshot] = None

        # 拖拽状态
        self._press_xy: Optional[tuple] = None
        self._dragging = False

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.configure(bg=MAGIC)
        self.win.attributes("-topmost", True)

        self.canvas = tk.Canvas(self.win, width=W, height=H, bg=MAGIC,
                                highlightthickness=0, cursor="hand2")
        self.canvas.pack()

        # 视觉引擎与图像缓冲（PhotoImage.paste 复用，避免每帧重建）
        self._skin_mgr = skins.SkinManager()
        self._skin_id = skins.load_skin_choice()
        self._art = self._skin_mgr.get_art(self._skin_id)
        self._photo = ImageTk.PhotoImage(self._art.compose(0, 0, False))
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

        # 初始位置：屏幕右侧偏上
        sx = self.win.winfo_screenwidth()
        self.win.geometry(f"{W}x{H}+{max(0, sx - W - 60)}+140")

        self._bind_events()
        self.win.update_idletasks()
        if IS_MAC:
            # macOS Aqua：整窗透明 + 系统透明画布，PNG alpha 直接合成
            try:
                self.win.attributes("-transparent", True)
                self.canvas.configure(bg="systemTransparent")
            except tk.TclError:
                self.win.configure(bg="#f2f5f7")
                self.canvas.configure(bg="#f2f5f7")
        else:
            try:
                self.win.attributes("-transparentcolor", MAGIC)
            except tk.TclError:
                pass  # 不支持时降级为普通窗口

        self._menu = tk.Menu(self.win, tearoff=0, font=(UI_FONT, 10))
        self._build_menu()
        self._tick()

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
        # v2.0.1：文字在前、勾选在后，用全角空格对齐，上下一致
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
        c = self.canvas
        c.bind("<Button-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_motion)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<Button-3>", self._on_right_click)
        if IS_MAC:
            c.bind("<Button-2>", self._on_right_click)
        c.bind("<MouseWheel>", self._on_wheel)
        c.bind("<Enter>", lambda e: self.win.focus_set())
        self.win.bind("<Left>", lambda e: self._nudge_angle(-ANGLE_STEP))
        self.win.bind("<Right>", lambda e: self._nudge_angle(ANGLE_STEP))
        self.win.bind("<space>", lambda e: self._toggle_power())

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

        # 扇叶转速（带惯性逼近目标）
        target_vel = SPIN_SPEED[snap.speed] if snap.power else 0
        self._spin_vel += (target_vel - self._spin_vel) * min(1.0, dt * 3)
        self._spin = (self._spin + self._spin_vel * dt) % 360

        # 扇头偏转：自动摇头时正弦扫动，否则平滑转向设备角度
        if snap.oscillation:
            target_yaw = YAW_VISUAL * math.sin(now * 0.9)
        else:
            target_yaw = (snap.angle - ANGLE_CENTER) / 90.0 * YAW_VISUAL
        self._yaw += (target_yaw - self._yaw) * min(1.0, dt * 6)

        self._draw(snap)
        self.win.after(40, self._tick)

    # ---------------------------------------------------------------- 绘制
    def _draw(self, snap: Snapshot) -> None:
        c = self.canvas
        self._photo.paste(self._art.compose(self._spin, self._yaw, snap.power))

        c.delete("dyn")
        on = snap.power

        # 状态文字（深色底条 + 白字，避免透明窗上 ClearType 粉边）
        if on:
            status = f"{snap.speed} 档"
            if snap.oscillation:
                status += " · 摇头中"
            elif snap.angle != ANGLE_CENTER:
                status += f" · 朝向 {snap.angle}°"
        else:
            status = "已关机 · 点击扇头开启"
        text_item = c.create_text(HEAD_CX, STATUS_Y, text=status, fill="white",
                                  font=(UI_FONT, 9), tags="dyn")
        x1, y1, x2, y2 = c.bbox(text_item)
        chip = c.create_rectangle(x1 - 8, y1 - 3, x2 + 8, y2 + 3,
                                  fill=CHIP_BG, outline=CHIP_BG, tags="dyn")
        c.tag_lower(chip, text_item)

        # 档位圆点（现代简约：白底描边 / 激活 teal 实心）
        for level, px in zip(range(SPEED_MIN, SPEED_MAX + 1), PIP_XS):
            active = on and level == snap.speed
            if active:
                fill, edge, fg = PIP_ON, PIP_ON_EDGE, "white"
            else:
                fill, edge, fg = PIP_OFF_FILL, PIP_OFF_EDGE, "#5b6673"
            c.create_oval(px - 10, PIP_Y - 10, px + 10, PIP_Y + 10,
                          fill=fill, outline=edge, width=1, tags="dyn")
            c.create_text(px, PIP_Y, text=str(level), fill=fg,
                          font=(UI_FONT, 9, "bold"), tags="dyn")
