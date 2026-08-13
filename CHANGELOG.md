# 变更日志

所有重要变更都会记录在此文件。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [2.0.3] - 2026-08-13

### 新增

- 前网罩层：放射格栅 + 外环 + 中心圆盖画在扇叶之前，格栅线半透明，
  扇叶在网罩内若隐若现，呈现「扇叶被网罩罩住」的前后层次
- 摇头立体投影：格栅随摇头角度做椭圆透视映射（x 半径 = r·cos(yaw)），
  中间辐条疏、两侧密，与扇头整体水平压扁一致，网罩呈现真实立体感
- 摇头连续渲染约 15.6ms/帧，静止帧命中格栅缓存约 4.9ms/帧

### 修复

- 移除 v2.0.1 遗留的 alpha 二值化（`-transparentcolor` 时代的兼容代码）：
  v2.0.2 已换 Win32 `UpdateLayeredWindow` 真逐像素 alpha，半透明格栅线
  不再被硬切成实色或直接消失

## [2.0.2] - 2026-08-13

### 修复

- 根治切换图片皮肤时的边缘"阴影"问题：Windows 改用 Win32
  `UpdateLayeredWindow` 实现真逐像素 alpha 透明（替换 `-transparentcolor`
  单一魔法色机制）。PNG 皮肤的半透明抗锯齿边缘现在正确合成到桌面，
  无杂色光晕。

### 变更

- 桌面挂件渲染统一为 PIL：风扇主体 + 状态文字 + 档位圆点全部用 PIL 绘制
  （替换 Canvas create_text/create_oval），两平台共用一套渲染逻辑
- macOS 分支保持 Aqua `-transparent` + ImageTk，行为不变

### 新增

- 真实风扇启停动画：S 形加速曲线（起步缓 → 中途快 → 接近目标收尾，
  约 1.5~2 秒到全速）、断电惯性滑行 + 摩擦减速（约 4.5 秒完全停住）、
  启动瞬间马达颤振（高频衰减抖动）

## [2.0.1] - 2026-08-13

### 变更

- 经典渲染视觉升级：统一左上光源，外环/笼体/扇叶/轴心/底座/立柱
  全部加入径向渐变高光与阴影，呈现真正的 3D 立体观感（替换 v2.0 的平面化风格）
- 皮肤子菜单布局调整：文字在前、勾选在后（用全角空格对齐），上下项位置一致

## [2.0.0] - 2026-08-12

### ⚠️ 破坏性变更

- **皮肤格式升级**：所有皮肤 PNG 必须由作者在外部工具（remove.bg / Photoshop / Figma /
  GIMP）提前导出**透明背景（RGBA**）。运行时不再做自动去背景。
  - 之前的算法路径（flood-fill / RGB 距离聚类 / 边缘 alpha 滤波）全部删除
  - `skin_processor.py` 从 220 行砍到 124 行
  - 不合规的 PNG 会抛出带明确指引的 `SkinFormatError`

### 新增

- `tools/build_skins.py` 离线皮肤生成器（rembg u2net ML 模型，PIL flood-fill 兜底）
- `docs/SKIN_GUIDE.md` 皮肤制作指南（推荐工具、导出步骤、常见错误对照表）
- `CHANGELOG.md` 变更日志
- `CONTRIBUTING.md` 贡献指南

### 变更

- README 全面重构为工程标准化版式（用户指南 / 构建 / 发布 / 贡献 / 路线图分章节）
- 内置皮肤源图移到 `assets/skins/_sources/`，运行时 PNG 由 `tools/build_skins.py` 生成
- 移除「打包与安装（给同事分发）」话术，改为面向发布维护者的「构建与发布」章节

### 修复

- v1.4.0 引入的换肤色差与不完整问题：**根本性**——通过把透明度生成从运行时移到设计时解决

### 迁移指南（v1.x → v2.0.0）

如果你之前上传过自定义皮肤（v1.x 的 `user_skin_dir/custom_*.png`）：

1. 启动 v2.0.0，错误信息会指向 SKIN_GUIDE.md
2. 用 remove.bg / Photoshop / Figma 重新导出带透明背景的 PNG
3. 在 FlowCC 中重新上传一次即可

4 张内置皮肤已自动用 `build_skins.py` 处理为透明 PNG，无需手动迁移。

## [1.5.1] - 2026-08-12

### 修复

- 皮肤去背景兼容性：渐变背景残留、边缘色差、内置皮肤 fallback

## [1.5.0] - 2026-08-12

### 新增

- macOS 适配（透明窗、图标、字体、配置目录、打包脚本）

## [1.4.0] - 2026-08-12

### 新增

- 换肤系统：内置四款图片皮肤 + 经典渲染 + 第三方上传自动适配
- 硬件搭建操作指南（`docs/硬件搭建操作指南.md`）

## [1.3.0] - 2026-08-12

### 新增

- 多传输接入：WiFi TCP / 蓝牙 BLE NUS，四模式连接条
- 传输层端到端测试（`tests/test_transports.py`）

## [1.2.0] - 2026-08-12

### 变更

- 挂件视觉升级：现代简约风格，PIL 分层渲染引擎

## [1.1.1] - 2026-08-12

### 新增

- 工程化打包：四叶草图标、PyInstaller + Inno Setup 安装包、GitHub remote

## [1.1.0] - 2026-08-12

### 变更

- 桌面风扇挂件（透明悬浮）变为主交互入口
- 控制中心兜底化

## [1.0.0] - 2026-08-12

### 新增

- 控制中心首版：模拟 / 串口双模式
- 三档风速、摇头开关、三种送风模式（恒定/自然/睡眠）
- 定时关机
- ESP32 参考固件（`firmware/esp32_fan/esp32_fan.ino`）

[Unreleased]: https://github.com/1524529306/Flow/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/1524529306/Flow/compare/v1.5.1...v2.0.0
[1.5.1]: https://github.com/1524529306/Flow/compare/v1.5.0...v1.5.1
[1.5.0]: https://github.com/1524529306/Flow/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/1524529306/Flow/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/1524529306/Flow/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/1524529306/Flow/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/1524529306/Flow/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/1524529306/Flow/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/1524529306/Flow/releases/tag/v1.0.0