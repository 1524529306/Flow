"""主窗口：FlowCC 桌面控制面板。

布局（自上而下）：
    设备连接条 —— 模拟 / 串口切换、端口与波特率、连接按钮
    风扇主面板 —— 大电源按钮、三档风速、摇头开关、实时输出指示
    送风模式   —— 恒定风 / 自然风 / 睡眠风
    定时关机   —— 取消 / 30 分钟 / 1 小时 / 2 小时 + 倒计时
    状态栏     —— 连接状态与错误提示

GUI 线程只负责渲染与转发点击；所有设备操作交给 FanController 的
worker 线程执行，界面每 200ms 轮询一次状态快照。
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional, Tuple

from .. import APP_NAME, TAGLINE, __version__
from ..controller import (
    MODE_LABELS,
    MODE_NATURAL,
    MODE_NORMAL,
    MODE_SLEEP,
    FanController,
    Snapshot,
)
from ..protocol import DEFAULT_BAUD, SPEED_MAX, SPEED_MIN

# ---------------------------------------------------------------------------
# 视觉常量
# ---------------------------------------------------------------------------
BG = "#eef3f7"
CARD = "#ffffff"
BORDER = "#d8e1ea"
ACCENT = "#0891b2"
ACCENT_DEEP = "#0e7490"
ACCENT_SOFT = "#e0f7fa"
TEXT = "#1f2937"
SUB = "#6b7280"
DANGER = "#dc2626"
IDLE = "#e2e8f0"

FONT = ("Microsoft YaHei UI", 10)
FONT_S = ("Microsoft YaHei UI", 9)
FONT_L = ("Microsoft YaHei UI", 12, "bold")

DEVICE_MODE_LABELS = ["模拟模式", "串口设备", "WiFi 设备", "蓝牙设备"]
DEVICE_MODE_KEYS = {
    "模拟模式": "mock",
    "串口设备": "serial",
    "WiFi 设备": "wifi",
    "蓝牙设备": "ble",
}
TIMER_OPTIONS = [(0, "取消"), (30, "30 分钟"), (60, "1 小时"), (120, "2 小时")]
BAUD_OPTIONS = ["9600", "19200", "57600", "115200"]


def _fmt_seconds(seconds: float) -> str:
    seconds = int(max(0, seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class MainWindow:
    def __init__(self, root: tk.Tk, controller: FanController,
                 config: Dict, on_close) -> None:
        self.root = root
        self.controller = controller
        self.config = config
        self.on_close = on_close

        self._last_snapshot: Optional[Snapshot] = None
        self._last_power_drawn: Optional[bool] = None
        saved_mode = config.get("device_mode", "mock")
        self._ui_device_mode = saved_mode if saved_mode in DEVICE_MODE_KEYS.values() else "mock"
        self._ble_devices: Dict[str, str] = {}
        self._ui_events: "queue.Queue[Tuple[str, Optional[str]]]" = queue.Queue()
        self._connect_thread: Optional[threading.Thread] = None

        root.title(f"{APP_NAME} · 桌面气流控制中心")
        root.configure(bg=BG)
        root.resizable(False, False)

        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TCombobox", font=FONT)
        style.configure("TRadiobutton", font=FONT, background=CARD)
        style.map("TRadiobutton", background=[("active", CARD)])

        self._build_ui()
        self._apply_device_mode(self._ui_device_mode, initial=True)
        self._poll()
        # v1.1：控制中心为兜底窗口，关闭=隐藏；真正退出走挂件右键菜单
        root.protocol("WM_DELETE_WINDOW", self.hide_window)

    def hide_window(self) -> None:
        """隐藏控制中心（桌面挂件仍在运行）。"""
        self.root.withdraw()

    def show_window(self) -> None:
        """从桌面挂件右键菜单打开控制中心。"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    # ------------------------------------------------------------------ UI
    def _card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg=CARD, padx=16, pady=12,
                        highlightbackground=BORDER, highlightthickness=1)
        tk.Label(card, text=title, bg=CARD, fg=SUB, font=FONT_S,
                 anchor="w").grid(row=0, column=0, columnspan=20, sticky="w")
        return card

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=BG, padx=18, pady=14)
        outer.pack(fill="both", expand=True)
        outer.grid_columnconfigure(0, weight=1)

        self._build_connection(outer)
        self._build_fan(outer)
        self._build_mode(outer)
        self._build_timer(outer)
        self._build_statusbar(outer)

    def _build_connection(self, parent: tk.Widget) -> None:
        card = self._card(parent, "设备连接")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        row = tk.Frame(card, bg=CARD)
        row.grid(row=1, column=0, columnspan=20, sticky="ew", pady=(6, 0))

        col = 0
        tk.Label(row, text="模式", bg=CARD, fg=TEXT, font=FONT).grid(row=0, column=col)
        col += 1
        self.device_mode_var = tk.StringVar(value=DEVICE_MODE_LABELS[0])
        self.combo_device_mode = ttk.Combobox(
            row, textvariable=self.device_mode_var, values=DEVICE_MODE_LABELS,
            state="readonly", width=9, font=FONT)
        self.combo_device_mode.grid(row=0, column=col, padx=(6, 14))
        self.combo_device_mode.bind("<<ComboboxSelected>>", self._on_device_mode)
        col += 1

        # 串口 / 蓝牙 共用的目标选择
        self.lbl_target = tk.Label(row, text="串口", bg=CARD, fg=TEXT, font=FONT)
        self.lbl_target.grid(row=0, column=col)
        col += 1
        self.port_var = tk.StringVar(value=self.config.get("port", ""))
        self.combo_port = ttk.Combobox(row, textvariable=self.port_var,
                                       width=14, font=FONT)
        self.combo_port.grid(row=0, column=col, padx=(6, 4))
        col += 1
        self.btn_refresh = tk.Button(row, text="刷新", font=FONT_S, bd=0,
                                     bg="#eef2f7", fg=TEXT, padx=8, pady=3,
                                     cursor="hand2", command=self._refresh_targets)
        self.btn_refresh.grid(row=0, column=col, padx=(0, 14))
        col += 1

        # 串口专用：波特率
        self.lbl_baud = tk.Label(row, text="波特率", bg=CARD, fg=TEXT, font=FONT)
        self.lbl_baud.grid(row=0, column=col)
        col += 1
        self.baud_var = tk.StringVar(value=str(self.config.get("baud", DEFAULT_BAUD)))
        self.combo_baud = ttk.Combobox(row, textvariable=self.baud_var,
                                       values=BAUD_OPTIONS, state="readonly",
                                       width=7, font=FONT)
        self.combo_baud.grid(row=0, column=col, padx=(6, 14))
        col += 1

        # WiFi 专用：地址 + 端口
        self.lbl_host = tk.Label(row, text="地址", bg=CARD, fg=TEXT, font=FONT)
        self.lbl_host.grid(row=0, column=col)
        col += 1
        self.wifi_host_var = tk.StringVar(value=self.config.get("wifi_host", ""))
        self.entry_host = ttk.Entry(row, textvariable=self.wifi_host_var,
                                    width=14, font=FONT)
        self.entry_host.grid(row=0, column=col, padx=(6, 4))
        col += 1
        self.lbl_wport = tk.Label(row, text="端口", bg=CARD, fg=TEXT, font=FONT)
        self.lbl_wport.grid(row=0, column=col)
        col += 1
        self.wifi_port_var = tk.StringVar(value=str(self.config.get("wifi_port", 3333)))
        self.entry_wport = ttk.Entry(row, textvariable=self.wifi_port_var,
                                     width=5, font=FONT)
        self.entry_wport.grid(row=0, column=col, padx=(6, 14))
        col += 1

        self.btn_connect = tk.Button(row, text="连接", font=FONT, bd=0,
                                     bg=ACCENT, fg="white", padx=18, pady=4,
                                     cursor="hand2", command=self._on_connect)
        self.btn_connect.grid(row=0, column=col)

        self._serial_widgets = (self.lbl_target, self.combo_port, self.btn_refresh,
                                self.lbl_baud, self.combo_baud)
        self._wifi_widgets = (self.lbl_host, self.entry_host,
                              self.lbl_wport, self.entry_wport)
        self._ble_widgets = (self.lbl_target, self.combo_port, self.btn_refresh)

        self.lbl_conn_hint = tk.Label(card, text="", bg=CARD, fg=SUB,
                                      font=FONT_S, anchor="w")
        self.lbl_conn_hint.grid(row=2, column=0, columnspan=20, sticky="w",
                                pady=(6, 0))

    def _build_fan(self, parent: tk.Widget) -> None:
        card = self._card(parent, "风扇控制")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # 左：电源大按钮
        left = tk.Frame(card, bg=CARD)
        left.grid(row=1, column=0, padx=(4, 26), pady=(8, 2))
        self.power_canvas = tk.Canvas(left, width=170, height=170, bg=CARD,
                                      highlightthickness=0, cursor="hand2")
        self.power_canvas.pack()
        self.power_canvas.bind("<Button-1>", lambda e: self._toggle_power())
        self.lbl_power = tk.Label(left, text="已关机", bg=CARD, fg=SUB,
                                  font=FONT_L)
        self.lbl_power.pack(pady=(4, 0))

        # 右：档位 / 摇头 / 输出指示
        right = tk.Frame(card, bg=CARD)
        right.grid(row=1, column=1, sticky="nsew", pady=(8, 2))

        tk.Label(right, text="风速档位", bg=CARD, fg=SUB, font=FONT_S,
                 anchor="w").grid(row=0, column=0, columnspan=3, sticky="w")
        self.speed_buttons: List[Tuple[int, tk.Button]] = []
        for level in range(SPEED_MIN, SPEED_MAX + 1):
            btn = tk.Button(right, text=f"{level} 档", font=("Microsoft YaHei UI", 11, "bold"),
                            width=7, height=2, bd=0, cursor="hand2",
                            command=lambda lv=level: self._on_speed(lv))
            btn.grid(row=1, column=level - SPEED_MIN, padx=(0, 10), pady=(4, 12))
            self.speed_buttons.append((level, btn))

        self.btn_osc = tk.Button(right, text="摇头：关", font=FONT, width=24,
                                 height=1, bd=0, cursor="hand2",
                                 command=self._toggle_osc)
        self.btn_osc.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.lbl_active = tk.Label(right, text="当前输出：--", bg=CARD,
                                   fg=SUB, font=FONT_S, anchor="w")
        self.lbl_active.grid(row=3, column=0, columnspan=3, sticky="w")

    def _build_mode(self, parent: tk.Widget) -> None:
        card = self._card(parent, "送风模式")
        card.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        row = tk.Frame(card, bg=CARD)
        row.grid(row=1, column=0, columnspan=20, sticky="w", pady=(6, 0))
        self.mode_var = tk.StringVar(value=MODE_NORMAL)
        self.mode_radios: List[ttk.Radiobutton] = []
        for mode, label in MODE_LABELS.items():
            radio = ttk.Radiobutton(row, text=label, value=mode,
                                    variable=self.mode_var,
                                    command=lambda m=mode: self._on_mode(m))
            radio.pack(side="left", padx=(0, 26))
            self.mode_radios.append(radio)

        self.lbl_mode_desc = tk.Label(card, text=self._mode_desc(MODE_NORMAL),
                                      bg=CARD, fg=SUB, font=FONT_S, anchor="w")
        self.lbl_mode_desc.grid(row=2, column=0, columnspan=20, sticky="w",
                                pady=(6, 0))

    @staticmethod
    def _mode_desc(mode: str) -> str:
        if mode == MODE_NATURAL:
            return "自然风：风速随时间随机起伏，模拟阵风，档位围绕设定值上下浮动。"
        if mode == MODE_SLEEP:
            return "睡眠风：每 20 分钟自动降低一档，直至最低档，越睡越轻柔。"
        return "恒定风：按设定档位持续稳定送风。"

    def _build_timer(self, parent: tk.Widget) -> None:
        card = self._card(parent, "定时关机")
        card.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        row = tk.Frame(card, bg=CARD)
        row.grid(row=1, column=0, columnspan=20, sticky="w", pady=(6, 0))
        self.timer_buttons: List[Tuple[int, tk.Button]] = []
        for minutes, label in TIMER_OPTIONS:
            btn = tk.Button(row, text=label, font=FONT_S, bd=0, padx=12,
                            pady=5, cursor="hand2",
                            command=lambda m=minutes: self._on_timer(m))
            btn.pack(side="left", padx=(0, 10))
            self.timer_buttons.append((minutes, btn))

        self.lbl_timer = tk.Label(row, text="未设置定时", bg=CARD, fg=SUB,
                                  font=FONT)
        self.lbl_timer.pack(side="left", padx=(16, 0))

    def _build_statusbar(self, parent: tk.Widget) -> None:
        bar = tk.Frame(parent, bg=BG)
        bar.grid(row=4, column=0, sticky="ew")
        self.lbl_status = tk.Label(bar, text="未连接", bg=BG, fg=SUB, font=FONT_S)
        self.lbl_status.pack(side="left")
        self.lbl_error = tk.Label(bar, text="", bg=BG, fg=DANGER, font=FONT_S)
        self.lbl_error.pack(side="left", padx=(16, 0))
        tk.Label(bar, text=f"{APP_NAME} v{__version__}", bg=BG, fg="#9aa7b4",
                 font=FONT_S).pack(side="right")

    # ----------------------------------------------------------- 电源按钮绘制
    def _draw_power(self, on: bool) -> None:
        canvas = self.power_canvas
        canvas.delete("all")
        cx = cy = 85
        radius = 66
        ring = ACCENT if on else IDLE
        fill = ACCENT_SOFT if on else "#ffffff"
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                           fill=fill, outline=ring, width=4)
        icon = ACCENT_DEEP if on else "#94a3b8"
        arc_r = 26
        canvas.create_arc(cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r,
                          start=120, extent=300, style="arc",
                          outline=icon, width=6)
        canvas.create_line(cx, cy - arc_r - 9, cx, cy - 6, fill=icon, width=6)

    # --------------------------------------------------------------- 交互回调
    def _toggle_power(self) -> None:
        snap = self._last_snapshot
        if snap and snap.connected:
            self.controller.set_power(not snap.power)

    def _on_speed(self, level: int) -> None:
        if self._last_snapshot and self._last_snapshot.connected:
            self.controller.set_speed(level)

    def _toggle_osc(self) -> None:
        snap = self._last_snapshot
        if snap and snap.connected:
            self.controller.set_oscillation(not snap.oscillation)

    def _on_mode(self, mode: str) -> None:
        self.lbl_mode_desc.configure(text=self._mode_desc(mode))
        self.controller.set_mode(mode)

    def _on_timer(self, minutes: int) -> None:
        self.controller.set_timer_minutes(minutes)

    def _on_device_mode(self, _event=None) -> None:
        mode = DEVICE_MODE_KEYS.get(self.device_mode_var.get(), "mock")
        if mode == "mock":
            self.controller.connect_mock()
        self._apply_device_mode(mode)

    def _apply_device_mode(self, mode: str, initial: bool = False) -> None:
        self._ui_device_mode = mode
        hints = {
            "mock": "模拟模式：内置虚拟风扇，无需硬件即可体验全部功能。",
            "serial": "串口模式：将刷好固件的 ESP32 经 USB 连接后，点击「连接」。",
            "wifi": "WiFi 模式：固件以 TCP 服务监听（默认 3333），输入设备 IP 后连接。",
            "ble": "蓝牙模式：点击「扫描」发现 FlowCC 设备后连接（需安装 bleak）。",
        }
        self.lbl_conn_hint.configure(text=hints[mode])
        self._set_mode_visibility(mode)
        if mode in ("serial", "ble") and not initial:
            self._refresh_targets()

    def _set_mode_visibility(self, mode: str) -> None:
        visible = {
            "mock": (),
            "serial": self._serial_widgets,
            "wifi": self._wifi_widgets,
            "ble": self._ble_widgets,
        }[mode]
        for widget in set(self._serial_widgets) | set(self._wifi_widgets):
            if widget in visible:
                widget.grid()
            else:
                widget.grid_remove()
        if mode == "serial":
            self.lbl_target.configure(text="串口")
            self.btn_refresh.configure(text="刷新")
        elif mode == "ble":
            self.lbl_target.configure(text="设备")
            self.btn_refresh.configure(text="扫描")

    def _refresh_targets(self) -> None:
        if self._ui_device_mode == "ble":
            self._scan_ble()
            return
        ports: List[str] = []
        try:
            from serial.tools.list_ports import comports
            ports = sorted(p.device for p in comports())
        except Exception:
            pass
        self.combo_port.configure(values=ports)
        current = self.port_var.get()
        if ports and current not in ports:
            self.port_var.set(ports[0])
        elif not ports:
            self.port_var.set("")
        if ports:
            self.lbl_conn_hint.configure(text=f"发现 {len(ports)} 个串口：{', '.join(ports)}")
        elif self._ui_device_mode == "serial":
            self.lbl_conn_hint.configure(
                text="未发现串口：请插入设备并安装 USB 转串口驱动（如 CH340 / CP2102）。")

    def _scan_ble(self) -> None:
        self.btn_refresh.configure(state="disabled", text="扫描中…")

        def _worker() -> None:
            try:
                from ..device.bledev import scan_ble_devices
                devices = scan_ble_devices()
            except Exception as exc:
                self._ui_events.put(("ble_result", f"ERROR:{exc}"))
                return
            self._ui_events.put(("ble_result", devices))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_ble_result(self, payload) -> None:
        self.btn_refresh.configure(state="normal", text="扫描",
                                   bg="#eef2f7", fg=TEXT)
        if isinstance(payload, str) and payload.startswith("ERROR:"):
            self.lbl_conn_hint.configure(
                text=f"蓝牙扫描失败：{payload[6:]}")
            return
        self._ble_devices = {}
        labels = []
        for address, name in payload:
            label = f"{name or 'FlowCC'}（{address}）"
            self._ble_devices[label] = address
            labels.append(label)
        self.combo_port.configure(values=labels)
        if labels:
            self.port_var.set(labels[0])
            self.lbl_conn_hint.configure(text=f"发现 {len(labels)} 个 FlowCC 蓝牙设备。")
        else:
            self.port_var.set("")
            self.lbl_conn_hint.configure(
                text="未发现 FlowCC 蓝牙设备：请确认固件已开启 BLE 且设备在附近。")

    def _on_connect(self) -> None:
        if self._ui_device_mode == "mock":
            self.controller.connect_mock()
            return
        snap = self._last_snapshot
        if snap and snap.connected and snap.device_label != "模拟设备":
            self.controller.disconnect()
            return
        if snap and snap.connecting:
            return

        mode = self._ui_device_mode
        if mode == "serial":
            port = self.port_var.get().strip()
            if not port:
                messagebox.showwarning(APP_NAME, "请先选择或输入串口。")
                return
            try:
                baud = int(self.baud_var.get())
            except ValueError:
                baud = DEFAULT_BAUD
            target = ("serial", port, baud)
        elif mode == "wifi":
            host = self.wifi_host_var.get().strip()
            if not host:
                messagebox.showwarning(APP_NAME, "请输入设备 IP 地址。")
                return
            try:
                port = int(self.wifi_port_var.get().strip() or 3333)
            except ValueError:
                port = 3333
            target = ("wifi", host, port)
        else:  # ble
            selection = self.port_var.get().strip()
            address = self._ble_devices.get(selection, "")
            if not address:
                messagebox.showwarning(APP_NAME, "请先扫描并选择蓝牙设备。")
                return
            target = ("ble", address)

        self._connect_thread = threading.Thread(
            target=self._connect_worker, args=(target,), daemon=True)
        self._connect_thread.start()

    def _connect_worker(self, target: tuple) -> None:
        try:
            kind = target[0]
            if kind == "serial":
                self.controller.connect_serial(target[1], target[2])
            elif kind == "wifi":
                self.controller.connect_wifi(target[1], target[2])
            else:
                self.controller.connect_ble(target[1])
            self._ui_events.put(("connected", kind))
        except Exception as exc:  # DeviceError 等
            self._ui_events.put(("error", str(exc)))

    # --------------------------------------------------------------- 轮询渲染
    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._ui_events.get_nowait()
                if kind == "error":
                    messagebox.showerror(APP_NAME, f"连接失败：\n{payload}")
                elif kind == "ble_result":
                    self._on_ble_result(payload)
        except queue.Empty:
            pass

        snapshot = self.controller.get_snapshot()
        self._last_snapshot = snapshot
        self._refresh(snapshot)
        self.root.after(200, self._poll)

    def _refresh(self, snap: Snapshot) -> None:
        # 电源按钮
        if self._last_power_drawn != snap.power:
            self._draw_power(snap.power)
            self._last_power_drawn = snap.power
        self.lbl_power.configure(
            text="已开机" if snap.power else "已关机",
            fg=ACCENT_DEEP if snap.power else SUB)

        # 档位按钮
        for level, btn in self.speed_buttons:
            if not snap.connected:
                btn.configure(state="disabled", bg="#f1f5f9", fg="#a8b3c0")
            elif level == snap.speed:
                btn.configure(state="normal", bg=ACCENT, fg="white",
                              activebackground=ACCENT_DEEP, activeforeground="white")
            else:
                btn.configure(state="normal", bg="#eef2f7", fg=TEXT,
                              activebackground=ACCENT_SOFT, activeforeground=TEXT)

        # 摇头
        if snap.connected:
            self.btn_osc.configure(state="normal")
            if snap.oscillation:
                self.btn_osc.configure(bg=ACCENT, fg="white", text="摇头：开",
                                       activebackground=ACCENT_DEEP,
                                       activeforeground="white")
            else:
                self.btn_osc.configure(bg="#eef2f7", fg=TEXT, text="摇头：关",
                                       activebackground=ACCENT_SOFT,
                                       activeforeground=TEXT)
        else:
            self.btn_osc.configure(state="disabled", bg="#f1f5f9", fg="#a8b3c0",
                                   text="摇头：关")

        # 输出指示
        if snap.power and snap.active_speed:
            suffix = ""
            if snap.mode != MODE_NORMAL:
                suffix = f"（{MODE_LABELS[snap.mode]}）"
            self.lbl_active.configure(
                text=f"当前输出：{snap.active_speed} 档{suffix}")
        else:
            self.lbl_active.configure(text="当前输出：--")

        # 模式
        if self.mode_var.get() != snap.mode:
            self.mode_var.set(snap.mode)
            self.lbl_mode_desc.configure(text=self._mode_desc(snap.mode))

        # 定时
        if snap.timer_remaining and snap.timer_remaining > 0:
            self.lbl_timer.configure(
                text=f"剩余 {_fmt_seconds(snap.timer_remaining)} 后关机",
                fg=ACCENT_DEEP)
        else:
            self.lbl_timer.configure(text="未设置定时", fg=SUB)
        active_total = snap.timer_total if snap.timer_remaining else None
        for minutes, btn in self.timer_buttons:
            if active_total is not None and minutes * 60 == active_total and minutes > 0:
                btn.configure(bg=ACCENT, fg="white",
                              activebackground=ACCENT_DEEP, activeforeground="white")
            elif minutes == 0 and active_total is None:
                btn.configure(bg="#eef2f7", fg=TEXT)
            else:
                btn.configure(bg="#eef2f7", fg=TEXT)

        # 状态栏
        if snap.connecting:
            self.lbl_status.configure(text="正在连接设备…", fg=SUB)
        elif snap.connected:
            extra = f"（固件 {snap.firmware}）" if snap.firmware else ""
            self.lbl_status.configure(
                text=f"已连接：{snap.device_label}{extra}", fg=ACCENT_DEEP)
        else:
            self.lbl_status.configure(text="未连接", fg=SUB)
        self.lbl_error.configure(text=snap.error or "")

        # 连接控件状态
        self._refresh_connect_controls(snap)

    def _refresh_connect_controls(self, snap: Snapshot) -> None:
        mode = self._ui_device_mode
        label_for_mode = {v: k for k, v in DEVICE_MODE_KEYS.items()}[mode]
        if self.device_mode_var.get() != label_for_mode:
            self.device_mode_var.set(label_for_mode)

        editable = {
            "mock": (),
            "serial": (self.combo_port, self.combo_baud),
            "wifi": (self.entry_host, self.entry_wport),
            "ble": (self.combo_port,),
        }[mode]
        real_connected = snap.connected and snap.device_label != "模拟设备"

        if mode == "mock":
            self.btn_refresh.configure(state="disabled", bg="#f1f5f9", fg="#a8b3c0")
            self.btn_connect.configure(state="disabled", bg="#b8c4d0",
                                       text="模拟运行中")
            return

        if snap.connecting:
            for widget in editable:
                widget.configure(state="disabled")
            self.btn_refresh.configure(state="disabled", bg="#f1f5f9", fg="#a8b3c0")
            self.btn_connect.configure(state="disabled", bg="#b8c4d0",
                                       text="连接中…")
            return

        if real_connected:
            for widget in editable:
                widget.configure(state="disabled")
            self.btn_refresh.configure(state="disabled", bg="#f1f5f9", fg="#a8b3c0")
            self.btn_connect.configure(state="normal", bg="#dc2626", text="断开")
        else:
            for widget in editable:
                widget.configure(state="normal")
            if mode != "ble" or self.btn_refresh.cget("text") == "扫描":
                self.btn_refresh.configure(state="normal", bg="#eef2f7", fg=TEXT)
            self.btn_connect.configure(state="normal", bg=ACCENT, text="连接")

    # ----------------------------------------------------------------- 关闭
    def request_close(self) -> None:
        snap = self._last_snapshot
        settings = {
            "device_mode": self._ui_device_mode,
            "port": self.port_var.get().strip(),
            "baud": int(self.baud_var.get() or DEFAULT_BAUD),
            "wifi_host": self.wifi_host_var.get().strip(),
            "wifi_port": int(self.wifi_port_var.get().strip() or 3333),
            "ble_address": self._ble_devices.get(self.port_var.get().strip(),
                                                 self.config.get("ble_address", "")),
            "speed": snap.speed if snap else self.config.get("speed", 2),
            "oscillation": snap.oscillation if snap else False,
            "angle": snap.angle if snap else self.config.get("angle", 90),
            "mode": snap.mode if snap else MODE_NORMAL,
        }
        try:
            self.on_close(settings)
        finally:
            self.root.destroy()
