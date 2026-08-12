# FlowCC · 桌面气流控制中心

> **软件先行、硬件随时对接**的桌面风扇控制软件。
> 今天就可以在**模拟模式**下体验全部功能；购齐 ESP32 + 风扇后，刷入参考固件，
> 切换到**串口 / WiFi / 蓝牙模式**即可控制实体风扇，软件无需任何改动。

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## 目录

- [用户指南](#用户指南)
  - [快速开始](#快速开始)
  - [功能一览](#功能一览)
  - [换肤](#换肤)
  - [对接实体硬件](#对接实体硬件)
- [构建与开发](#构建与开发)
  - [开发环境](#开发环境)
  - [项目结构](#项目结构)
  - [运行测试](#运行测试)
- [发布](#发布)
  - [打包独立 exe](#打包独立-exe)
  - [编译安装包](#编译安装包)
  - [生成内置皮肤](#生成内置皮肤)
  - [版本管理](#版本管理)
- [贡献](#贡献)
- [路线图](#路线图)
- [排错](#排错)

---

## 用户指南

### 快速开始

#### Windows 用户（推荐）

下载最新安装包 → https://github.com/1524529306/Flow/releases → 双击 `FlowCC-Setup-*.exe` 完成安装。

#### 想自己跑源码

```bash
git clone https://github.com/1524529306/Flow.git
cd Flow
pip install -r requirements.txt
python -m flowcc --smoke     # 冒烟测试，2.5 秒后自动退出
python -m flowcc             # 正常运行
```

或双击 `run.bat`。

#### macOS 用户

```bash
brew install python-tk       # Tk ≥ 8.6
pip3 install -r requirements.txt pillow
python3 -m flowcc            # 或双击 run.command
```

启动后桌面上出现一个透明迷你风扇（**模拟模式，无需硬件**）：

- 点击扇头：开关机；滚轮或底部圆点：换档
- 鼠标悬停后按 ←/→：手动摆头；拖拽：移动挂件
- 右键：打开控制中心 / 自动摇头 / 换肤 / 退出

控制中心默认隐藏，右键「打开控制中心」即可进行串口连接、送风模式、定时等完整配置。

### 功能一览

- **桌面风扇挂件**：透明悬浮小风扇（默认现代简约风格），扇叶按档位旋转、摆头可见，是日常主交互入口
- **挂件交互**：点击扇头开关机、滚轮/圆点换档、悬停 + ←/→ 手动摆头、拖拽移动、右键菜单
- **电源控制**：1~3 档风速、摇头开关（含 0~180° 手动摆头）
- **多传输**：模拟设备 / USB 串口 / WiFi（TCP 3333）/ 蓝牙 BLE NUS，同一套协议无缝切换
- **换肤系统**：内置奶油可爱图片皮肤 + 经典渲染，自定义 PNG 自动校验并适配
- **送风模式**：恒定风 / 自然风（风速随机起伏）/ 睡眠风（每 20 分钟自动降一档）
- **定时关机**：30 分钟 / 1 小时 / 2 小时，带倒计时显示
- **偏好记忆**：档位、摇头、角度、模式、各连接参数自动保存

### 换肤

右键桌面挂件 →「皮肤」：内置奶油可爱与经典渲染可切换。

选「上传新皮肤…」使用自己的 PNG，**PNG 必须含 Alpha 通道（透明背景）**。
导出工具与详细要求见 [docs/SKIN_GUIDE.md](docs/SKIN_GUIDE.md)。

内置皮肤的源图位于 `assets/skins/_sources/`，运行时 PNG 由 `tools/build_skins.py` 离线生成。

### 对接实体硬件

完整搭建流程见 `docs/硬件搭建操作指南.md`（BOM、接线图、烧录、联调、验收、排错）。

简版：

1. 按 `firmware/esp32_fan/esp32_fan.ino` 顶部注释接线（ESP32 + MOSFET + 风扇 + 摇头舵机）
2. 用 Arduino IDE 安装 ESP32 开发板支持（核心版本 ≥ 3.0），选择对应板型后烧录固件
3. 打开 Windows 设备管理器确认串口号（如 COM3，CH340/CP2102 需装驱动）
4. 软件「设备连接」中选择「串口设备」，选中端口，波特率 115200，点击「连接」

也可以直接用串口助手向设备发送协议命令调试：

```
PWR 1      开机
SPD 2      2 档
OSC 1      摇头开
ANG 120    手动摆头到 120°（自动摇头随之关闭）
STATE?     查询状态
PING       心跳
```

完整协议见 [FlowCC 产品文档](docs/FlowCC产品文档.docx) 第 5 节，或 `flowcc/protocol.py` 顶部注释。

---

## 构建与开发

### 开发环境

| 工具 | 版本 | 说明 |
|---|---|---|
| Python | 3.10+（3.13 已验证）| tkinter / pyserial / pillow / pyinstaller |
| Git | 最新 | 推送 / PR 用 |
| Inno Setup | 6.x | 编译 `.exe` 安装包（仅 Windows）|
| Arduino IDE | 2.x | 烧录 ESP32 固件 |

克隆与依赖：

```bash
git clone https://github.com/1524529306/Flow.git
cd Flow
pip install -r requirements.txt
# 可选：rembg 用于离线重新生成内置皮肤
pip install "rembg[cpu]"
```

### 项目结构

```
FlowCC/
├── flowcc/                 软件软件主体
│   ├── app.py              入口与组装
│   ├── controller.py       控制器：状态机、定时、场景引擎、心跳
│   ├── protocol.py         串口协议编解码
│   ├── config.py           配置持久化
│   ├── device/             设备抽象层
│   │   ├── base.py         FanDevice 接口
│   │   ├── mock.py         模拟设备（无硬件可用）
│   │   ├── serialdev.py    真实串口设备
│   │   ├── wifi.py         WiFi (TCP) 设备
│   │   └── ble.py          蓝牙 BLE 设备
│   └── gui/                GUI：主窗 + 挂件 + 皮肤系统
├── firmware/esp32_fan/     ESP32 参考固件（Arduino）
├── installer/              Inno Setup 安装包脚本
├── tools/                     离线工具
│   └── build_skins.py      内置皮肤离线生成器
├── launcher.py             PyInstaller 打包入口
├── tests/                  单元测试
├── docs/                   产品文档 + 皮肤指南 + 硬件搭建指南
├── CHANGELOG.md            版本变更日志
├── CONTRIBUTING.md         贡献指南
├── AGENTS.md               AI / 协作者项目手册
├── requirements.txt        Python 依赖
└── assets/skins/           内置皮肤（透明 PNG 运行时）
    └── _sources/            内置皮肤源图（不透明原始素材）
```

### 运行测试

```bash
python -m unittest discover -s tests -t . -v
```

冒烟测试（启动界面 2.5 秒后自动退出）：

```bash
python -m flowcc --smoke
```

### 修改协议（务必四同步）

改协议时必须**同时**更新：

1. `flowcc/protocol.py` — Python 编解码
2. `firmware/esp32_fan/esp32_fan.ino` — ESP32 固件
3. `tests/test_protocol.py` — 单元测试
4. `docs/FlowCC产品文档.docx`（由根目录 gen_docx.py 生成，勿直接改 docx）

且必须**保持向后兼容**（旧帧可解析）。

---

## 发布

### 打包独立 exe

```bash
python -m PyInstaller --noconfirm --onefile --windowed --name FlowCC ^
  --icon=flowcc.ico --add-data "flowcc.ico;." --add-data "assets/skins;assets/skins" ^
  --hidden-import=serial --hidden-import=serial.tools --hidden-import=serial.tools.list_ports ^
  launcher.py
```

产物：`dist/FlowCC.exe`（约 37MB）。

### 编译安装包

需要 Inno Setup 6（https://jrsoftware.org/isdload.php）。

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\flowcc.iss
```

产物：`release/FlowCC-Setup-<version>.exe`（约 37MB 压缩后）。

### 生成内置皮肤

```bash
# 检查环境（是否安装了 rembg）
python -m tools.build_skins --check

# 重新处理 _sources/ 下的所有 PNG
python -m tools.build_skins

# 处理单张
python -m tools.build_skins assets/skins/_sources/new_skin.png
```

输出到 `assets/skins/<原文件名>`（覆盖）。模型首次运行下载约 176MB，缓存到 `%USERPROFILE%/.u2net/`。

### 版本管理

- **语义化版本**（semver）：`MAJOR.MINOR.PATCH`
  - MAJOR：不兼容的 API/行为变更（如 v1.x → v2.0 皮肤格式变更）
  - MINOR：向后兼容的功能新增
  - PATCH：向后兼容的 bug 修复
- **发布流程**：
  1. 更新 `flowcc/__version__` + `installer/flowcc.iss` 的 `AppVersion`
  2. 在 `CHANGELOG.md` 顶部新增条目
  3. `git commit -m "FlowCC vX.Y.Z: <一句话>"`
  4. `git tag -a vX.Y.Z -m "<详细说明>"`
  5. 推到 GitHub：`git push origin main --tags`
  6. 在 GitHub Releases 创建 Release，上传安装包作为 asset

---

## 贡献

详见 [CONTRIBUTING.md](CONTRIBUTING.md)：开发流程、Commit 规范、PR 流程。

---

## 路线图

- **M2 硬件原型**：采购材料、烧录固件、串口联调
- **M3 完整版功能**：温度联动智能调速、每日定时任务、场景自定义
- **M4 体验增强**：托盘常驻、开机自启、固件 OTA

---

## 排错

| 现象 | 原因 | 解决 |
|---|---|---|
| `皮肤 PNG 必须是 RGBA 含透明通道` | 文件是 JPG 改后缀 / RGB PNG | 见 [SKIN_GUIDE.md](docs/SKIN_GUIDE.md) |
| 串口连不上 | 端口被占用 / 驱动未装 | 关闭其他串口软件；装 CH340/CP2102 驱动 |
| `PIL.UnidentifiedImageError` | 文件不是有效 PNG | 用 ImageMagick `identify` 检查文件头 |
| exe 启动闪退 | 缺 VC++ 运行库 | 装 https://aka.microsoft.com/vs/17/release/vc_redist.x64.exe |

更多问题提 Issue。

---

## 许可证

MIT License — 详见仓库 LICENSE 文件。