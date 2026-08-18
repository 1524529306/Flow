#!/bin/bash
# FlowCC macOS 本地构建脚本（需在 macOS 上运行）
# 产出：dist/FlowCC.app + dist/FlowCC-<version>-macOS.dmg
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(python3 -c "import flowcc; print(flowcc.__version__)")
echo "==> Building FlowCC v${VERSION} for macOS"

# 依赖检查
python3 -c "import tkinter" 2>/dev/null || { echo "ERROR: tkinter 不可用，请安装 python.org 版 Python"; exit 1; }
python3 -m pip install --quiet pyinstaller pyserial pillow

# 生成 .icns 图标
echo "==> 生成 FlowCC.icns ..."
python3 packaging/macos/make_icns.py soft_log.png FlowCC.icns

# 构建 .app
echo "==> PyInstaller building .app ..."
python3 -m PyInstaller --noconfirm packaging/macos/FlowCC-macOS.spec

# 当前机器架构，用于 DMG 命名
ARCH=$(uname -m)

# ad-hoc 签名（免开发账号，本地可运行；分发仍需正式签名/公证）
echo "==> Ad-hoc codesign ..."
codesign --force --deep --sign - "dist/FlowCC.app" 2>/dev/null || echo "    (codesign skipped)"

# 打 DMG
echo "==> Creating DMG ..."
hdiutil create -volname "FlowCC" \
    -srcfolder "dist/FlowCC.app" \
    -ov -format UDZO \
    "dist/FlowCC-${VERSION}-${ARCH}.dmg"

echo "==> Done:"
ls -lh dist/FlowCC.app "dist/FlowCC-${VERSION}-${ARCH}.dmg"
echo ""
echo "提示：分发给其他用户需 Apple Developer 账号做正式签名 + 公证，"
echo "      否则对方首次打开需 右键->打开 或 系统设置->隐私与安全性 允许。"
