#!/bin/bash
# FlowCC macOS 安装脚本（双击此文件即可）
# 作用：修复可执行权限 -> 拷贝到 /Applications -> 首次启动
cd "$(dirname "$0")" || exit 1

echo "==> FlowCC 安装中..."

if [ ! -d "FlowCC.app" ]; then
    echo "ERROR: 未找到 FlowCC.app，请确认 zip 已完整解压。" >&2
    read -r -p "按回车退出..." _
    exit 1
fi

chmod +x FlowCC.app/Contents/MacOS/FlowCC
xattr -cr FlowCC.app 2>/dev/null

echo "==> 拷贝到 /Applications ..."
rm -rf "/Applications/FlowCC.app"
cp -R FlowCC.app /Applications/

echo "==> 安装完成，正在启动 FlowCC ..."
open /Applications/FlowCC.app

read -r -p "FlowCC 已启动（如无窗口请看屏幕上方挂件）。按回车关闭此窗口..." _
