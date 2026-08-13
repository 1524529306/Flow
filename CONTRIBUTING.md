# 贡献指南

欢迎为 FlowCC 做出贡献！本文档面向**想要提交代码、新功能、Bug 修复**的朋友。

---

## 开发流程

1. **Fork** 本仓库到你自己的 GitHub 账户
2. **Clone** 你的 fork：
   ```bash
   git clone https://github.com/<your-name>/Flow.git
   cd Flow
   git remote add upstream https://github.com/1524529306/Flow.git
   ```
3. **创建功能分支**（不要直接在 main 上改）：
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **编码 + 写测试**（见下方约定）
5. **本地全量测试通过**：
   ```bash
   python -m unittest discover -s tests -t .
   ```
6. **提交 + Push**（commit 规范见下方）
7. **提 PR**：在你的 fork 页面点 "Compare & pull request"，描述清楚改了什么、为什么

---

## Commit 规范

我们用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/) 风格，但不强求：

```
<类型>: <一句话描述>

可选正文：详细说明动机、影响、关联 issue
```

| 类型 | 用途 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat: 添加温度联动智能调速` |
| `fix` | Bug 修复 | `fix: 串口断开后自动重连失效` |
| `docs` | 文档变更 | `docs: 补充 macOS 安装说明` |
| `refactor` | 重构（无行为变更）| `refactor: 拆分协议编解码为独立函数` |
| `test` | 测试相关 | `test: 增加 BLE 断线重连用例` |
| `chore` | 杂项 | `chore: 升 pillow 依赖到 10.4` |

**禁止**：

- ❌ "去 AI 痕迹" / "fix §3" / 反向标注（此地无银三百两）
- ❌ 单一 commit 包含不相关变更
- ❌ 标题超过 72 字符

---

## 代码约定

### 项目结构约定（参见 [AGENTS.md](AGENTS.md)）

1. **设备抽象优先**：GUI/控制器只依赖 `FanDevice` 接口
2. **协议变更四同步**：`flowcc/protocol.py` + `firmware/*.ino` + `tests/` + 产品文档
3. **线程模型**：所有设备操作入队 worker 执行，GUI 只读 Snapshot 渲染
4. **交互验证**：UI/挂件改动用桌面截屏目检（注意 ClearType 粉边问题）

### 风格

- Python：PEP 8 + 4 空格缩进；中文 docstring 允许
- 文件头用 UTF-8 BOM-less；Windows 下 Git 自动转 CRLF，不必担心
- 字符串用直引号 `"` / `'`
- import 顺序：标准库 → 第三方 → 项目内
- 测试覆盖：每个新功能至少 1 个 happy path + 1 个 edge case

### 跑测试

```bash
python -m unittest discover -s tests -t . -v
```

冒烟：

```bash
python -m flowcc --smoke
```

---

## 提交 Bug / Feature 请求

提 Issue 时请包含：

- **环境**：Windows 版本 / macOS 版本 / Python 版本 / 是否打包版
- **复现步骤**：一步一步列出
- **期望行为**
- **实际行为**（带日志 / 截图）
- **可能的原因**（如有）

---

## 沟通

- **小问题**：直接提 Issue
- **设计讨论**：开 Issue 标 `discussion`
- **安全问题**：私下联系维护者，不公开 Issue

---

## 许可证

提交 PR 即表示你同意按 [MIT 许可证](LICENSE) 贡献你的代码。

---

**再次感谢你的贡献！🎉**