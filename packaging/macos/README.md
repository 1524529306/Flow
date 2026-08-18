# FlowCC macOS 构建说明

## 三种分发方式

| 方式 | 产物 | 是否需 Mac | 说明 |
|------|------|-----------|------|
| 源码 .app 包 | FlowCC-macOS-2.2.13.zip | 否（已生成） | 需目标机装有 Python 3.8+，首次运行自动装 pyserial |
| 本地 PyInstaller | FlowCC.app + .dmg | 是 | 独立二进制，无需 Python，用 `packaging/macos/build.sh` |
| GitHub Actions 云构建 | .dmg | 否 | 推送后手动触发 workflow，macOS runner 编译 |

## 方式一：源码 .app 包（当前可用）

`dist/FlowCC-macOS-2.2.13.zip` 解压后得到 `FlowCC.app`，拖入 `/Applications` 即可。

要求：目标 Mac 装有 Python 3.8+（`python.org` 安装包自带 tkinter；系统自带 `/usr/bin/python3` 也带）。
首次双击运行时 launcher 会自动 `pip install --user pyserial`。

注意：从浏览器下载的 zip 解压后，首次打开可能被 Gatekeeper 拦截，
右键 FlowCC.app -> 打开 -> 再点「打开」即可放行（源码模式无签名）。

## 方式二：有 Mac 时本地编译（推荐，产物独立）

```bash
cd Flow
bash packaging/macos/build.sh
```

产出 `dist/FlowCC.app`（独立二进制）和 `dist/FlowCC-<version>-macOS.dmg`。

## 方式三：GitHub Actions 云构建（无需 Mac）

仓库已含 `.github/workflows/build-macos.yml`。推送后在 GitHub 仓库
Actions 页面 -> Build macOS -> Run workflow 手动触发，
构建完成后在该次运行页面底部 Artifacts 下载 `FlowCC-macOS`（含 .dmg）。

## 签名与公证（正式分发需要）

无签名的包用户首次打开需手动放行。正式分发流程：

1. Apple Developer 账号（$99/年）
2. `codesign --sign "Developer ID Application: ..." --options runtime dist/FlowCC.app`
3. `xcrun notarytool submit FlowCC.dmg --apple-id ... --wait`
4. `xcrun stapler staple FlowCC.dmg`
