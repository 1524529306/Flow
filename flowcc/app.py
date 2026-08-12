"""应用入口：组装配置、控制器与主窗口。"""
from __future__ import annotations

import argparse
import logging
import sys
import tkinter as tk
from pathlib import Path

from . import APP_NAME, __version__
from .config import load_config, save_config
from .controller import FanController
from .gui.mainwindow import MainWindow
from .gui.widget import FanWidget

logger = logging.getLogger(__name__)


def find_app_icon() -> Path | None:
    """按优先级查找应用图标：exe 同目录 > PyInstaller 包内 > 项目根目录。"""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "flowcc.ico")
        candidates.append(Path(sys._MEIPASS) / "flowcc.ico")
    candidates.append(Path(__file__).resolve().parents[1] / "flowcc.ico")
    for path in candidates:
        if path.exists():
            return path
    return None


def apply_app_icon(root: tk.Tk) -> None:
    icon = find_app_icon()
    if icon is None:
        return
    try:
        # default= 让所有子窗口（含桌面挂件）继承同一图标
        root.iconbitmap(default=str(icon))
    except tk.TclError:
        logger.warning("设置应用图标失败: %s", icon, exc_info=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME, description="智能桌面风扇控制软件")
    parser.add_argument("--smoke", action="store_true",
                        help="冒烟测试模式：启动 2.5 秒后自动退出")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger.info("%s v%s 启动", APP_NAME, __version__)

    config = load_config()
    controller = FanController()
    controller.apply_preset(
        speed=config.get("speed"),
        oscillation=config.get("oscillation"),
        mode=config.get("mode"),
        angle=config.get("angle"),
    )
    controller.start()
    controller.connect_mock()  # 启动默认进入模拟模式，保证无硬件也能立即使用

    root = tk.Tk()
    apply_app_icon(root)
    window = MainWindow(root, controller, config, on_close=save_config)
    # v1.1：桌面挂件为主交互入口，控制中心默认隐藏、作为兜底配置
    root.withdraw()
    FanWidget(root, controller,
              on_open_center=window.show_window,
              on_quit=window.request_close)
    if args.smoke:
        root.after(2500, window.request_close)
    root.mainloop()

    controller.stop()
    logger.info("%s 已退出", APP_NAME)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
