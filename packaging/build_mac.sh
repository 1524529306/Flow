#!/bin/bash
# 在 macOS 上打包 FlowCC 独立应用（.app 束）：
#   1) 先装依赖：brew install python-tk 或确保系统 Tk ≥ 8.6
#      python3 -m pip install -r requirements.txt pillow pyinstaller bleak
#   2) 在项目根目录执行本脚本，产物在 dist/FlowCC.app（或 FlowCC 可执行文件）
#   3) 分发：zip -ry FlowCC-mac.zip dist/FlowCC.app
cd "$(dirname "$0")/.." || exit 1

python3 -m PyInstaller --noconfirm --onedir --windowed --name FlowCC \
  --add-data "soft_log.png:." \
  --hidden-import=serial --hidden-import=serial.tools --hidden-import=serial.tools.list_ports \
  launcher.py

echo "打包完成：dist/FlowCC.app（或 dist/FlowCC）"
