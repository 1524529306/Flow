#!/bin/bash
# FlowCC macOS 启动脚本（双击或 ./run.command）
cd "$(dirname "$0")" || exit 1
python3 -m flowcc "$@"
