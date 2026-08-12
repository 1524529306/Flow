"""应用入口：组装配置、控制器与主窗口。"""
from __future__ import annotations

import argparse
import logging
import tkinter as tk

from . import APP_NAME, __version__
from .config import load_config, save_config
from .controller import FanController
from .gui.mainwindow import MainWindow

logger = logging.getLogger(__name__)


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
    )
    controller.start()
    controller.connect_mock()  # 启动默认进入模拟模式，保证无硬件也能立即使用

    root = tk.Tk()
    window = MainWindow(root, controller, config, on_close=save_config)
    if args.smoke:
        root.after(2500, window.request_close)
    root.mainloop()

    controller.stop()
    logger.info("%s 已退出", APP_NAME)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
