@echo off
rem FlowCC 一键启动（Windows）
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d %~dp0
python -m flowcc %*
