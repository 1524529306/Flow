# FlowCC · 智能桌面风扇控制软件（桌面气流控制中心）

一套「软件先行、硬件随时对接」的桌面风扇控制方案。今天就可以在**模拟模式**下
体验全部功能；等你购齐 ESP32、风扇等材料后，刷入参考固件，切换到**串口模式**
即可控制实体风扇，软件无需任何改动。

## 功能一览（标准版 v1.3）

- 桌面风扇挂件：透明悬浮小风扇（现代简约风格），扇叶按档位旋转、摆头可见，是日常主交互入口
- 挂件交互：点击扇头开关机、滚轮/圆点换档、悬停 + ←/→ 手动摆头、拖拽移动、右键菜单
- 电源开关、1~3 档风速、摇头开关（含 0~180° 手动摆头）
- 四种连接方式：模拟设备 / USB 串口 / WiFi（TCP）/ 蓝牙 BLE，同一套协议无缝切换
- 换肤系统：内置现代简约等四款图片皮肤 + 经典渲染，右键挂件可换肤；
  「上传新皮肤」任意风扇图片自动去背景、定位扇头并适配动画
- 送风模式：恒定风 / 自然风（风速随机起伏）/ 睡眠风（每 20 分钟自动降一档）
- 定时关机：30 分钟 / 1 小时 / 2 小时，带倒计时显示
- 控制中心：右键挂件「打开控制中心」，作为兜底的完整配置面板
- 偏好记忆：档位、摇头、角度、模式、各连接参数自动保存

## 快速开始（模拟模式，无需硬件）

```bat
pip install -r requirements.txt
run.bat
```

启动后桌面上出现一个透明悬浮的迷你风扇（模拟模式，无需硬件）：

- 点击扇头：开关机；滚轮或底部圆点：换档
- 鼠标悬停后按 ←/→：手动摆头；拖拽：移动挂件
- 右键：打开控制中心 / 自动摇头 / 退出

控制中心默认隐藏，右键「打开控制中心」即可进行串口连接、送风模式、定时等完整配置。

## 换肤（v1.4）

右键桌面挂件 →「皮肤」：内置四风格与经典渲染可切换；选「上传新皮肤…」
选择任意立式风扇 PNG，自动完成去背景、裁剪、扇头检测并叠加旋转叶影动画，
处理结果缓存复用。默认皮肤为「现代简约」。

## 对接实体硬件

完整搭建流程见 `docs/硬件搭建操作指南.md`（BOM、接线图、烧录、联调、验收、排错）。

1. 按 `firmware/esp32_fan/esp32_fan.ino` 顶部注释接线（ESP32 + MOSFET + 风扇 + 摇头舵机）。
2. 用 Arduino IDE 安装 ESP32 开发板支持（核心版本 ≥ 3.0），选择对应板型后烧录固件。
3. 打开 Windows 设备管理器确认串口号（如 COM3，CH340/CP2102 需装驱动）。
4. 在软件「设备连接」中选择「串口设备」，选中端口，波特率 115200，点击「连接」。

不想刷固件时，也可以直接用串口助手向设备发送协议命令调试，例如：

```
PWR 1      开机
SPD 2      2 档
OSC 1      摇头开
ANG 120    手动摆头到 120°（自动摇头随之关闭）
STATE?     查询状态
PING       心跳
```

完整协议见《FlowCC 产品文档》第 5 节，或 `flowcc/protocol.py` 顶部注释。

## 连接方式（四种传输，同一协议）

固件 `firmware/esp32_fan/esp32_fan.ino` 顶部 `FLOWCC_TRANSPORT` 三选一编译：

- **SERIAL（默认）**：USB 串口 115200。软件「串口设备」模式选择 COM 口连接。
- **WIFI**：填写 `WIFI_SSID/WIFI_PASS` 编译烧录；上电后串口监视器打印 IP。
  软件「WiFi 设备」模式输入 IP + 端口 3333 连接，无需接线、隔着桌子也能控。
- **BLE**：编译 BLE 后设备广播名 `FlowCC`。软件「蓝牙设备」模式扫描连接，
  走 Nordic UART Service。源码运行需 `pip install bleak`；
  打包版 exe 未内置 bleak，蓝牙模式请用源码版（WiFi/串口不受影响）。

软件侧由 `flowcc/device/` 的设备抽象统一承载：模拟 / 串口 / WiFi / 蓝牙
可在控制中心热切换，挂件与场景引擎完全无感。

## 运行测试

```bat
python -m unittest discover -s tests -t . -v
```

冒烟测试（启动界面 2.5 秒后自动退出）：

```bat
python -m flowcc --smoke
```

## 项目结构

```
FlowCC/
├── flowcc/                 # 软件主体
│   ├── app.py              # 入口与组装
│   ├── controller.py       # 控制器：状态机、定时、场景引擎、心跳
│   ├── protocol.py         # 串口协议编解码
│   ├── config.py           # 配置持久化
│   ├── device/             # 设备抽象层
│   │   ├── base.py         #   FanDevice 接口
│   │   ├── mock.py         #   模拟设备（无硬件可用）
│   │   └── serialdev.py    #   真实串口设备
│   └── gui/mainwindow.py   # tkinter 控制面板
│   └── gui/widget.py       # 透明桌面风扇挂件（主交互入口）
├── firmware/esp32_fan/     # ESP32 参考固件（Arduino）
├── installer/              # Inno Setup 安装包脚本（flowcc.iss + zh_cn.isl）
├── launcher.py             # PyInstaller 打包入口
├── soft_log.png / flowcc.ico  # 应用 Logo 与图标
├── tests/                  # 单元测试（协议 + 控制器）
└── requirements.txt        # 依赖：pyserial
```

## 打包与安装（给同事分发）

1. 打包独立 exe（无需 Python 环境）：

```bat
python -m PyInstaller --noconfirm --onefile --windowed --name FlowCC ^
  --icon=flowcc.ico --add-data "flowcc.ico;." ^
  --hidden-import=serial --hidden-import=serial.tools --hidden-import=serial.tools.list_ports ^
  launcher.py
```

2. 编译中文安装向导（需 Inno Setup 6）：

```bat
ISCC.exe installer\flowcc.iss
```

3. 把 `release\FlowCC-Setup-1.3.0.exe` 发给同事：下一步 → 安装，
   自动创建桌面快捷方式（四叶草图标）与开始菜单，免管理员权限，自带卸载程序。

## GitHub 协作

远程仓库已配置：https://github.com/1524529306/Flow.git 。
本机 git 走代理 127.0.0.1:7890，推送前先开启 Clash，然后：

```bat
git push -u origin main --tags
```

首次推送按提示登录 GitHub 授权一次即可（凭据会保存）。

## 后续路线

- M2 硬件原型：采购材料、烧录固件、串口联调
- M3 完整版功能：温度联动智能调速、每日定时任务、场景自定义
- M4 体验增强：托盘常驻、开机自启、固件 OTA
