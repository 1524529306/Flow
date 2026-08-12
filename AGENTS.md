# AGENTS.md - FlowCC 项目协作手册

> 本文件面向参与本项目的 AI 助手（WorkBuddy、QwenWork 等）与人类协作者。
> 进入项目请先读本文件，再看 README.md 与 docs/FlowCC产品文档.docx。

## 项目一句话

FlowCC = 桌面气流控制中心。Python(tkinter) 桌面软件 + ESP32 参考固件，
通过 ASCII 串口协议控制 DIY 桌面风扇；桌面透明挂件为主交互入口，控制中心为兜底配置。

## 当前状态

- 软件版本 v1.3.0（tag v1.2.0 视觉升级 / v1.3.0 多传输），里程碑 M1.3 已完成。
- 传输层：模拟 / 串口 / WiFi(TCP 3333) / BLE(NUS) 四模式，协议同一套；bleak 为可选依赖。
- M2（硬件原型联调）待启动：硬件未购齐，设备抽象层保证软件可独立演进。
- 仓库：https://github.com/1524529306/Flow.git （origin 已配置）。

## 目录速览

- flowcc/            软件主体（controller 状态机 / device 抽象 / gui 挂件与控制中心 / protocol 协议）
- firmware/          ESP32 Arduino 参考固件（协议逐条对应）
- installer/         Inno Setup 脚本（flowcc.iss + zh_cn.isl 中文覆盖包）
- dist/ release/     构建产物（git 忽略）：FlowCC.exe、FlowCC-Setup-*.exe
- docs/              产品文档 docx（由工作区根 gen_docx.js 生成，勿手改 docx）
- tests/             unittest 单元测试

## 常用命令（项目根目录执行）

- 测试：`python -m unittest discover -s tests -t .`
- 冒烟：`python -m flowcc --smoke`（或 `dist\FlowCC.exe --smoke`）
- 打包 exe：`python -m PyInstaller --noconfirm --onefile --windowed --name FlowCC --icon=flowcc.ico --add-data "flowcc.ico;." --hidden-import=serial --hidden-import=serial.tools --hidden-import=serial.tools.list_ports launcher.py`
- 编译安装包：`"C:\Users\Win10\InnoSetup6\ISCC.exe" installer\flowcc.iss`
- 图标再生成：soft_log.png 改后用 pillow 转 flowcc.ico（去浅色背景转透明，多尺寸）

## 架构约定（务必遵守）

1. 设备抽象优先：GUI/控制器只依赖 FanDevice 接口；新功能必须同时落地
   MockFanDevice 与 SerialFanDevice，保持「无硬件可开发」。
2. 协议变更四同步：改协议必须同步更新 protocol.py、firmware/*.ino、
   tests/、产品文档生成脚本，保持向后兼容（旧帧可解析）。
2b. 传输层改动必须补 tests/test_transports.py 的端到端用例（FakeSerial / 本地 TCP）。
3. 线程模型：所有设备操作入队由 worker 执行；GUI 只读 Snapshot 渲染。
4. 交互验证：UI/挂件改动用桌面截屏目检（透明窗注意 ClearType 粉边问题，
   文字需加实色底条）。
5. 版本管理：功能里程碑打 git tag；安装包文件名与 AppVersion 同步。

## 本机环境备忘

- Python：D:\python\python.exe（3.13，tkinter 8.6，pyserial/pillow/pyinstaller 已装）。
- 网络代理：git 走 127.0.0.1:7890，需用户手动开启 Clash，否则 github 不通。
- 用户桌面在 D:\桌面（非默认路径）；Inno Setup 装在 C:\Users\Win10\InnoSetup6。
- Git Bash 会吞 `/FLAG` 参数（变 C:/Program Files/Git/FLAG），调用 exe 用 `//FLAG`。
- 控制台 GBK 编码，中文输出乱码属正常，不影响文件内容。
