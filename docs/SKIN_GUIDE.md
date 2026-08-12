# 皮肤制作指南

FlowCC 桌面风扇挂件支持自定义图片皮肤。本文档面向**想要提交新皮肤或自己做皮肤的用户**。

> **v2.0 起，所有皮肤 PNG 必须由作者在外部工具中提前导出透明背景。运行时不再做去背景处理。**

---

## 1. 皮肤要求

| 项目 | 要求 |
|---|---|
| 文件格式 | **PNG**（必须含 Alpha 通道，即 RGBA 模式）|
| 背景 | **必须透明**，不要白底 / 渐变 / 实色 |
| 画布 | 建议 400×500 或更大的正方形 / 竖长方形 |
| 主体 | 风扇居中偏上（占上方 60%）|
| 主体颜色 | 任意，运行时不影响 |

### 如何验证透明背景

打开 PNG 后：

- **macOS**：Preview → 「显示 alpha 通道」（或拖到 Safari 看是否有棋盘格背景）
- **Windows**：Photos 应用 / 浏览器打开（透明区域显示灰白棋盘格）
- **Python**：
  ```python
  from PIL import Image
  im = Image.open("your_skin.png")
  assert im.mode == "RGBA", "必须是 RGBA 模式"
  alpha = im.split()[3]
  transparent_ratio = sum(1 for a in alpha.getdata() if a < 64) / (im.width * im.height)
  assert transparent_ratio > 0.05, f"透明像素仅 {transparent_ratio:.1%}，疑似无透明背景"
  ```

---

## 2. 推荐导出工具

按易用性排序：

### 🥇 remove.bg（在线，最简单）

1. 打开 https://remove.bg
2. 上传你的风扇图
3. 点「Download」→ 默认就是 **PNG with transparent background**
4. 改名（如 `my_fan.png`），完成

免费版有尺寸限制，但 400×500 远远够用。

### 🥈 Photoshop

1. 打开图片
2. 用「魔棒 / 快速选择 / 钢笔」选中背景
3. `Select → Inverse`（反选，主体）
4. 添加图层蒙版（白色 = 显示，黑色 = 隐藏）
5. `File → Export → Export As → PNG`，勾选「Transparency」

### 🥉 Figma（免费）

1. 打开 https://figma.com，新建文件
2. 把风扇图拖进来
3. 选中背景 → `Delete` 即可
4. `Export → PNG`，Format = **PNG**，勾选「Include background」（**不勾**就对了）

### GIMP（免费开源）

1. 打开图片
2. `Layer → Transparency → Add Alpha Channel`
3. 用「Fuzzy Select / Select by Color」选中背景
4. `Edit → Clear`（删除选区）
5. `File → Export As → .png`

---

## 3. 在 FlowCC 中使用

1. 启动 FlowCC，桌面出现风扇挂件
2. **右键**挂件 → **皮肤** → **上传新皮肤…**
3. 选择你导出的透明 PNG
4. 软件校验通过后立即生效

### 常见错误

| 错误信息 | 原因 | 解决 |
|---|---|---|
| `皮肤 PNG 必须是 RGBA 含透明通道（当前 mode=RGB）` | 文件是 JPG 改后缀 / RGB PNG | 重新导出，**勾选透明背景** |
| `皮肤 PNG 缺少透明背景（透明像素仅 X%）` | 导出时没勾透明 / 用了 JPG | 重新导出 |
| `主体尺寸过小` | 风扇画得太小 | 画布放大、主体占画布 > 40% |
| `未检测到风扇主体` | 整张图近乎全透明 | 检查导出步骤，主体颜色不要是纯白 |

---

## 4. 内置皮肤源图维护

如果你是项目维护者，想修改 4 张内置皮肤（`style_A/B/C/D`）：

1. 把新的不透明原图覆盖到 `assets/skins/_sources/<name>.png`
2. 运行离线生成器：
   ```bash
   python -m tools.build_skins
   ```
3. 脚本会用 `rembg`（u2net 模型）处理源图，输出到 `assets/skins/<name>.png`
4. 打包时 PyInstaller 会自动把 `assets/skins/` 打包进 exe

模型首次运行自动下载到 `%USERPROFILE%/.u2net/u2net.onnx`（约 176MB），后续无需重下。

### 兜底策略

如果 `rembg` 安装失败或离线环境无法下载模型，脚本会自动回退到 PIL `flood-fill`：
- 对**单色背景**效果尚可
- 对**渐变 / 复杂背景**效果不佳，建议安装 `rembg`：

  ```bash
  pip install "rembg[cpu]"
  ```

---

## 5. 提交皮肤到项目

如果你设计了一款很棒的皮肤想分享：

1. 把源图（不透明的也行）放到 `assets/skins/_sources/`，文件名 `<your_skin>.png`
2. 用 `tools/build_skins.py` 生成透明版本
3. 提一个 PR，附上：
   - 渲染后效果截图（不同档位、摇头角度）
   - 皮肤简介（名称 / 风格 / 适合场景）
4. 维护者会审查主体定位是否合理、风格是否符合项目调性

---

**更多问题？** 提 Issue 或看 [README § 排错](../README.md#排错)。