# FlowCC · 桌面气流控制中心

> **软件先行、硬件随时对接**的桌面风扇控制软件。
> 桌面透明挂件为主交互入口，控制中心为兜底配置；
> 购齐 ESP32 + 风扇后刷入参考固件，即可通过 USB 串口 / WiFi / 蓝牙控制实体风扇，
> 软件无需任何改动。

[![Version](https://img.shields.io/badge/version-3.0.0-blue)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)]()
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 目录

- [快速开始](#快速开始)
- [功能特性](#功能特性)
- [连接实体硬件](#连接实体硬件)
- [项目结构](#项目结构)
- [开发](#开发)
- [构建与发布](#构建与发布)
- [文档导航](#文档导航)
- [路线图](#路线图)
- [排错](#排错)
- [许可证](#许可证)

---

## 快速开始

#### Windows（推荐，无需装 Python）

下载最新安装包：[GitHub Releases](https://github.com/1524529306/Flow/releases) →
`FlowCC-Setup-3.0.0.exe`，下一步 → 安装，自动创建桌面快捷方式（四叶草图标）。

#### macOS

仓库自带 `dist/macos-install/`（FlowCC.app + 一键安装脚本）；详细的环境准备、安装、
打包与排错见 [docs/macOS安装指南.md](docs/macOS安装指南.md)。

#### 源码运行

```bash
git clone https://github.com/1524529306/Flow.git
cd Flow
pip install -r requirements.txt pillow
python -m flowcc            # Windows；macOS 用 python3 -m flowcc 或 run.command
```

启动后桌面上出现透明迷你风扇（**模拟模式，无需硬件**）：

- 点击扇头 / 空格键：开关机；滚轮或底部圆点：换档
- 鼠标悬停后按 ←/→：手动摆头；拖拽：移动挂件
- 右键：打开控制中心 / 自动摇头 / 风声静音 / 退出

## 功能特性

- **桌面挂件主入口**：真逐像素透明悬浮窗（Windows / macOS），3D 经典渲染
  （前网罩椭圆透视 + 真实启停动画：S 形加速、惯性滑行、启动颤振）
- **挂件交互**：点击扇头开关机、滚轮/圆点换档、悬停 + ←/→ 手动摆头、拖拽、右键菜单
- **风声模拟**：按档位循环播放合成风声（1 档轻缓、3 档呼啸），可一键静音
- **电源控制**：1~3 档风速、摇头开关（含 0~180° 手动摆头）
- **四种连接**：模拟设备 / USB 串口 / WiFi（TCP 3333）/ 蓝牙 BLE（NUS），同一协议无缝切换
- **送风模式**：恒定风 / 自然风（随机起伏）/ 睡眠风（每 20 分钟自动降一档）
- **定时关机**：30 分钟 / 1 小时 / 2 小时，带倒计时
- **偏好记忆**：档位、摇头、角度、模式、风声静音、连接参数自动保存

## 连接实体硬件

完整搭建流程（BOM、接线图、烧录、联调、验收、排错）见
[docs/硬件搭建操作指南.md](docs/硬件搭建操作指南.md)。

固件 `firmware/esp32_fan/esp32_fan.ino` 顶部 `FLOWCC_TRANSPORT` 三选一编译：

| 传输 | 固件配置 | 软件连接方式 |
|---|---|---|
| USB 串口 | `SERIAL`（默认）| 控制中心「串口设备」，115200 |
| WiFi | `WIFI` + 填写 SSID/密码 | 「WiFi 设备」填 IP + 端口 3333 |
| 蓝牙 | `BLE`（广播名 FlowCC）| 「蓝牙设备」扫描连接（源码版需 `pip install bleak`）|

协议为 ASCII 行协议，可直接用串口助手调试：

```
PWR 1      开机
SPD 2      2 档
OSC 1      摇头开
ANG 120    手动摆头到 120°（自动摇头随之关闭）
STATE?     查询状态
PING       心跳
```

完整协议见 [docs/FlowCC产品文档.docx](docs/FlowCC产品文档.docx) 第 5 节，或 `flowcc/protocol.py` 顶部注释。

## 项目结构

```
FlowCC/
├── flowcc/                 软件主体
│   ├── app.py              入口与组装
│   ├── controller.py       控制器：状态机、定时、场景引擎、心跳
│   ├── protocol.py         串口协议编解码
│   ├── config.py           跨平台配置持久化
│   ├── device/             设备抽象层（FanDevice + LineProtocolDevice）
│   │   ├── mock.py         模拟设备
│   │   ├── serialdev.py    USB 串口
│   │   ├── wifidev.py      WiFi (TCP)
│   │   └── bledev.py       蓝牙 BLE (bleak)
│   └── gui/                界面：mainwindow 控制中心 / widget 挂件 /
│                            widget_art 渲染引擎 / winlayered 真透明窗 / audio 风声
├── assets/audio/           三档风声样本（离线合成，无版权）
├── firmware/esp32_fan/     ESP32 参考固件（Arduino）
├── installer/              Inno Setup 安装包脚本（Windows）
├── packaging/macos/        macOS 打包脚本与 .icns 生成
├── dist/macos-install/     macOS 安装包（FlowCC.app + 安装.command）
├── launcher.py             PyInstaller 打包入口
├── tests/                  单元测试（协议 / 控制器 / 传输 / 渲染）
├── tools/gen_wind_sound.py 风声样本离线生成器
├── docs/                   文档（见下方「文档导航」）
├── CHANGELOG.md            当前版本线变更日志
├── docs/历史版本记录.md     v1.0.0 ~ v2.2.13 历史归档
├── AGENTS.md               AI / 协作者项目手册
└── requirements.txt        Python 依赖
```

## 开发

```bash
python -m unittest discover -s tests -t .    # 全量测试
python -m flowcc --smoke                     # 冒烟测试（2.5 秒后自动退出）
```

**修改协议务必四同步**：`flowcc/protocol.py` + `firmware/esp32_fan/esp32_fan.ino` +
`tests/test_protocol.py` + 产品文档生成脚本，且必须保持向后兼容（旧帧可解析）。

## 构建与发布

#### Windows

```bash
# 1. 独立 exe（需 PyInstaller）
python -m PyInstaller --noconfirm --onefile --windowed --name FlowCC ^
  --icon=flowcc.ico --add-data "flowcc.ico;." ^
  --hidden-import=serial --hidden-import=serial.tools --hidden-import=serial.tools.list_ports ^
  launcher.py

# 2. 中文安装向导（需 Inno Setup 6）
ISCC.exe installer\flowcc.iss    # 产物 release\FlowCC-Setup-<version>.exe
```

#### macOS

```bash
./packaging/macos/build.sh       # 产物 dist/FlowCC.app，zip 分发
```

推 tag 后 GitHub Actions（`.github/workflows/build-macos.yml`）自动产出 macOS 构建。

#### 版本管理（自 3.0.0 起）

- 语义化版本：**3.0.x** = bug 修复，**3.1.x** = 向后兼容的新功能
- 版本记录只维护当前版本线（CHANGELOG.md）；历史版本归档在 docs/历史版本记录.md
- 发布流程：
  1. 更新 `flowcc/__version__` 与 `installer/flowcc.iss`
  2. `CHANGELOG.md` 顶部新增条目
  3. `git commit -m "FlowCC vX.Y.Z: <一句话>"`
  4. `git tag -a vX.Y.Z -m "<说明>"` && `git push origin main --tags`
  5. `gh release create vX.Y.Z release\FlowCC-Setup-X.Y.Z.exe --title "FlowCC X.Y.Z" --notes-file docs\release-X.Y.Z.md`

## 文档导航

| 文档 | 内容 |
|---|---|
| [docs/硬件搭建操作指南.md](docs/硬件搭建操作指南.md) | BOM、接线图、烧录、联调、验收、排错 |
| [docs/macOS安装指南.md](docs/macOS安装指南.md) | macOS 环境准备、安装、打包、常见问题 |
| [docs/FlowCC产品文档.docx](docs/FlowCC产品文档.docx) | 产品规格、交互、架构、协议、里程碑 |
| [docs/历史版本记录.md](docs/历史版本记录.md) | v1.0.0 ~ v2.2.13 历史变更归档 |
| [docs/design/](docs/design/) | 挂件视觉风格样图 |
| [CHANGELOG.md](CHANGELOG.md) | 当前版本线变更日志 |
| [AGENTS.md](AGENTS.md) | AI / 协作者项目手册 |

## 路线图

- **M2 硬件原型**：采购材料、烧录固件、串口/WiFi 联调
- **M3 完整版功能**：温度联动智能调速、每日定时任务、场景自定义
- **M4 体验增强**：托盘常驻、开机自启、固件 OTA

## 排错

| 现象 | 原因 | 解决 |
|---|---|---|
| 串口连不上 | 端口被占用 / 驱动未装 | 关闭其它串口软件；装 CH340/CP2102 驱动 |
| 蓝牙扫描无结果 | 固件非 BLE 版 / bleak 缺失 | 固件切 `BLE`；源码版 `pip install bleak` |
| exe 启动闪退 | 缺 VC++ 运行库 | 装 https://aka.microsoft.com/vs/17/release/vc_redist.x64.exe |
| mac 无法打开 app | Gatekeeper | `xattr -cr /Applications/FlowCC.app` |

更多问题提 Issue。

## 许可证

MIT License — 详见 [LICENSE](LICENSE)。
