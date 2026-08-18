"""应用配置持久化（跨平台数据目录下的 config.json）。"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULTS: Dict[str, Any] = {
    "device_mode": "mock",          # mock | serial
    "port": "",
    "baud": 115200,
    "wifi_host": "",
    "wifi_port": 3333,
    "ble_address": "",
    "speed": 2,
    "oscillation": False,
    "angle": 90,
    "mode": "normal",
    "mute": False,
}


def app_data_dir() -> Path:
    """跨平台应用数据目录（配置等）。"""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or str(Path.home()))
        folder = base / "FlowCC"
    elif sys.platform == "darwin":
        folder = Path.home() / "Library" / "Application Support" / "FlowCC"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        folder = base / "FlowCC"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def config_path() -> Path:
    return app_data_dir() / "config.json"


def load_config() -> Dict[str, Any]:
    data = dict(DEFAULTS)
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except FileNotFoundError:
        pass  # 首次启动尚无配置文件，使用默认值
    except (OSError, ValueError):
        logger.info("读取配置失败，使用默认配置", exc_info=True)
    return data


def save_config(data: Dict[str, Any]) -> None:
    try:
        with open(config_path(), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except OSError:
        logger.warning("保存配置失败", exc_info=True)
