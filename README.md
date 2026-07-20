# UTA Agent

UTA Agent 是一个本地优先的实验性 AI Agent，尝试让 AI 不再只是完成一次对话，而是能够在长期交互中保存经验、理解用户偏好，并根据真实反馈持续调整后续行为。

项目围绕四个核心机制构建：

- **持续记忆**：通过实时记忆与正式记忆保存长期指令、用户偏好和重要上下文，并支持搜索、版本记录与回滚。
- **Skill 演化**：将重复出现的任务沉淀为可复用 Skill，通过候选版本、使用反馈和效果评估逐步优化。
- **反馈闭环**：记录用户的满意、不满意及文字反馈，将反馈归因到实际使用的记忆和 Skill 版本。
- **Token 生存机制**：为 AI 设置读取和输出资源账户，使其能够感知资源消耗，并探索任务质量与长期资源之间的平衡。

UTA Agent 采用 React、FastAPI、SQLite、Tauri 等技术构建，支持 OpenAI 兼容模型接口、本地工具调用、结构化执行轨迹以及 Windows 桌面运行。对话、工具执行、Token 账本、记忆版本和 Skill 版本均保存在本地，便于审计、恢复和研究。

这个项目并不意味着已经实现真正的自主进化或 AGI。它更像一次系统级持续学习实验：在底层模型不发生改变的情况下，通过记忆、反馈、工具、Skill 和版本管理，让整个 Agent 在连续交互中表现出逐步适应和积累经验的能力。

项目目前处于实验版本，并已暂停持续维护。仓库保留了完整的设计思路、工程实现和测试记录，可作为本地 Agent、长期记忆系统和反馈驱动学习机制的研究参考。

> [!WARNING]
> 本项目目前是 `0.1.0-alpha` 实验版本，接口、数据库结构和桌面打包方式仍可能变化。它尚未经过第三方安全审计，Windows 安装包也未进行代码签名，请勿用于生产环境、敏感数据或不可恢复的自动化任务。

## 项目定位

- 本地优先：业务数据默认保存在本机 SQLite 和受限 Workspace。
- 可审计：消息、工具调用、Token 账本、记忆版本、Skill 版本与执行轨迹保留结构化关联。
- 可恢复：后台整理失败不会覆盖旧记忆，数据库迁移和桌面数据目录相互独立。
- Provider 可替换：支持 OpenAI 兼容接口；请自行评估所选服务商的隐私、计费和可用性。

这不是官方 OpenAI 产品，也不隶属于 Hermes Agent 或任何模型服务商。

## 当前状态

第 0—8 阶段已完成；第 9 阶段的 Tauri/Sidecar/NSIS 本地链路已实现，最终真实模型桌面复验仍待完成。React 前端现可作为 Tauri Windows 桌面应用运行，自动启动隐藏的 PyInstaller `--onedir` FastAPI Sidecar、选择本地空闲端口、等待健康检查并在关闭时优雅回收。会话、回合、消息、工具执行、Token 交易、反馈、实时/正式记忆、认知 Job、Skill Registry 与执行轨迹保存在真实 SQLite。准确进度和验收边界见 [`docs/development-status.md`](docs/development-status.md)。

已实现页面：

- `/chat/:conversationId`：创建/切换/重命名/删除会话，流式回答、工具执行、满意/不满意、文字反馈、停止生成、失败重试和刷新恢复。
- `/memory`：正式 18,000 字符与实时 2,000 字符双层记忆，搜索、锁定、归档、恢复、版本历史、回滚及 consumed 来源链路。
- `/skills`：真实 Skill Registry、搜索、创建/编辑、锁定、归档、稳定/候选统计、版本差异控制与回滚。
- `/activity`：真实认知 Job 与“发现问题→候选→评估→晋升/拒绝/回滚”的 Skill 审计链。
- `/settings`：持久化 OpenAI 兼容 Base URL、模型、超时和输出上限，显示 Workspace/工具，并从同一 WAL 读快照下载脱敏 JSON；桌面 API Key 存入 Windows 凭据管理器，开发模式仍只读取环境变量。

## 目录

```text
apps/web/             React 图形前端
apps/desktop/         Tauri Windows Shell 与安装器配置
services/api/         FastAPI 服务
services/desktop_sidecar.py  桌面 Sidecar 启动、迁移与优雅退出
migrations/           Alembic 数据库迁移
packages/contracts/   跨端结构化契约（后续阶段扩展）
tests/backend/        后端测试
tests/e2e/            独立进程、真实 SQLite 的完整端到端链路
docs/                 架构、数据库和开发状态
```

## 本地开发

前置要求：Node.js 22+、Python 3.12+、npm、uv。

```powershell
npm install
uv sync --dev
uv run alembic upgrade head
$env:OPENAI_API_KEY = Read-Host -MaskInput
uv run uvicorn services.api.app.main:app --reload
```

另开一个终端：

```powershell
npm run dev:web
```

访问 `http://localhost:5173`。API 健康检查位于 `http://127.0.0.1:8000/api/health`。

模型 Base URL 应填 OpenAI 兼容 API 根路径，例如 `https://api.example.com/v1`；Provider 会在后面追加 `/chat/completions`。

不要把 API Key 写进 `.env.example`、SQLite、命令参数、Issue 或提交记录。开发模式仅从当前进程环境变量读取；桌面模式使用 Windows 凭据管理器。

工具只能访问 `SURVIVAL_AGENT_WORKSPACE_PATH` 配置的 Workspace（默认 `./workspace`）。路径必须为相对路径；写入已有文件必须由模型显式传入 `overwrite=true`。Workspace 内容是本地用户数据，不提交 Git。

Token 生存账本内部使用整数 Units（100 Units = 1 Token）：读取与输出初始余额分别为 1,000,000,000 和 100,000,000 Token。系统不会因余额不足自动拒绝任务，也不会把缓存或推理明细重复计入 Provider 的总 Usage。

实时记忆只对明显长期指令进行确定性检测，不额外调用模型。有效增量最多 2,000 个 Unicode Code Point；重复表达合并占用，溢出内容保留为 `deferred_capacity`。正式记忆最多 18,000 字符，主回合按核心 4,000 + FTS5 相关 6,000 + 实时 2,000 动态检索。整理失败或版本冲突不会覆盖旧记忆；历史 revision、snapshot 和归档内容永久保留但不占生效额度。

Skill 与记忆分库存储，不占 20,000 字符额度。单轮最多确定性加载 3 个、合计 8,000 字符，并把实际 Revision IDs 写入 execution trace。候选版本固定每第 10 次匹配任务试用；至少 5 次有效使用后才按 60% 满意度、20% 任务完成、15% 客观验证、5% Token 效率评估。用户锁定、手动晋升、拒绝和回滚始终高于自动决策。

Worker 使用 `BEGIN IMMEDIATE` 原子领取任务，冲突状态按 10/30 秒重新读取最新版本，第三次失败后等待用户重试；应用重启会回收旧进程的未完成领取。`logs/app.log`、`agent.log`、`worker.log`、`error.log` 与数据导出共享敏感信息清理规则，不保存完整密钥或 Authorization Header。恢复与 E2E 操作见 `docs/testing-and-recovery.md`。

## 验证

```powershell
npm run lint:web
npm run test:web
npm run build:web
uv run ruff check .
uv run pytest
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
npm run build:sidecar
uv run python tests/e2e/phase9_sidecar_flow.py
```

完整 Windows 安装包使用 `npm run desktop:build` 生成到 `apps/desktop/src-tauri/target/release/bundle/nsis/`。构建脚本固定 PyInstaller 6.16.0；如本机配置了代理，包管理器会沿用当前进程的 `HTTP_PROXY/HTTPS_PROXY`，代理凭据不得写入仓库。桌面数据位于 `%APPDATA%/SurvivalAgent/{data,logs,workspace,backups}`，卸载不会把业务数据当作安装资源删除。更多说明见 `docs/desktop-packaging.md`。

真实密钥只允许保存在开发进程环境变量或桌面端 Windows 凭据管理器中，不进入 SQLite、日志、Sidecar 参数、导出、安装包或 Git。

## 已知限制

- 仅对 Windows 11 桌面链路进行了本地验收，macOS 与 Linux 尚未支持。
- Windows 安装包未签名，SmartScreen 可能显示未知发布者。
- OpenAI 兼容 Provider 的流式 Usage 和错误格式并不完全统一，部分服务商可能需要适配。
- Cognitive Worker 依赖模型严格输出 JSON；无效结果会被拒绝并保留旧记忆，等待重试。
- 当前没有稳定发布渠道、自动更新、遥测、远程同步或多用户权限系统。

后续计划见 [`ROADMAP.md`](ROADMAP.md)，安全报告方式见 [`SECURITY.md`](SECURITY.md)。

## 参与项目

提交 Issue 或 Pull Request 前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)。公开仓库不代表已经授予开源许可；当前版权与使用边界见 [`LICENSE`](LICENSE)。
