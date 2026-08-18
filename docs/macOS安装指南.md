# FlowCC macOS 安装指南

> 适用版本：FlowCC 3.0.0+。macOS 12+（Monterey 及以上），Intel 与 Apple 芯片均可。

## 一、环境准备（一次性）

```bash
# 1. 安装 Homebrew（如已装可跳过）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装带 Tk 的 Python（Tk ≥ 8.6，挂件透明窗必需）
brew install python-tk

# 3. 确认版本
python3 --version        # ≥ 3.9
python3 -m tkinter       # 应弹出一个空白小窗；报错则 python-tk 未生效
```

> 也可用 python.org 官方安装包（勾选 "Install Tcl/Tk 8.6"），
> 与 Homebrew 版二选一即可，切勿混用。

## 二、获取代码

```bash
git clone https://github.com/1524529306/Flow.git
cd Flow
```

## 三、安装依赖

```bash
python3 -m pip install --user -r requirements.txt pillow
# 蓝牙模式额外需要（可选）：
python3 -m pip install --user bleak
```

## 四、启动

```bash
chmod +x run.command
./run.command          # 或直接双击 run.command
```

启动后桌面右上出现透明风扇挂件（主交互入口）；右键挂件 →「打开控制中心」进入配置面板。
macOS 透明窗走 Aqua `-transparent` 方案，若个别系统版本不支持会自动降级为浅色普通窗口，功能不受影响。

## 五、打包成 .app（分发给其他 Mac 用户）

```bash
# 在项目根目录执行
./packaging/macos/build.sh
# 产物：dist/FlowCC.app（内含图标与全部依赖，目标机无需安装 Python）
zip -ry FlowCC-mac-3.0.0.zip dist/FlowCC.app
```

分发给同事后，若系统提示"无法打开，因为无法验证开发者"（Gatekeeper）：

```bash
xattr -cr /Applications/FlowCC.app     # 或右键 → 打开 → 仍要打开
```

仓库已配置 GitHub Actions（.github/workflows/build-macos.yml），推 tag 后自动产出
macOS 构建产物，可直接在 Actions 页面下载，无需本地打包。

## 六、首次使用检查清单

| 事项 | 说明 |
|---|---|
| 蓝牙权限 | 首次扫描会弹系统授权框，点允许；否则到「系统设置 → 隐私与安全性 → 蓝牙」开启 |
| 串口设备 | USB 转串口设备显示为 `/dev/cu.usbserial-*` 或 `/dev/cu.SLAB_USBtoUART`，控制中心直接选 |
| WiFi 设备 | 与 ESP32 同一局域网，填设备 IP + 端口 3333 |
| 配置目录 | `~/Library/Application Support/FlowCC/`（config.json 与皮肤缓存） |
| 声音 | 风声模拟默认开启，右键挂件或控制中心可关 |

## 七、常见问题

- **`_tkinter` 找不到 / 打开即闪退**：`brew install python-tk` 后重新打开终端再运行。
- **挂件是普通方块窗口**：该 macOS 版本不支持 Aqua 透明属性，属正常降级，功能不变。
- **中文字体显示为方块**：系统装 PingFang 即可（macOS 自带），PIL 会按路径自动加载。
- **蓝牙扫描无结果**：确认固件为 BLE 版（FLOWCC_TRANSPORT BLE）且广播名 FlowCC、距离 <5 米。
