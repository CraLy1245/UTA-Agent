# Survival Agent

Survival Agent 是一个本地运行、图形优先、数据可恢复的 AI Agent。项目采用独立实现，不 Fork Hermes Agent；第一版按阶段交付，先确保基础架构稳定，再逐步加入对话、工具、Token 生存账本、记忆与 Skill 演化。

## 当前状态

第 0、1、2、3、4、5 阶段已完成。前端使用正式 REST/WebSocket API，会话、回合、消息、工具执行、Token 交易、反馈、实时记忆与执行轨迹保存在 SQLite。OpenAI 兼容 Provider 支持 SSE 流式输出与结构化工具调用；每轮真实 Usage 使用 Token Units 精确扣款，满意只返还一次 108%，不满意只进入质量反馈通道。明确的“请记住”“以后不要”和纠正语义会立即形成实时记忆，从下一回合动态注入；实际注入的 revision ID 会写入 execution trace。

已实现页面：

- `/chat/:conversationId`：创建/切换/重命名/删除会话，流式回答、工具执行、满意/不满意、文字反馈、停止生成、失败重试和刷新恢复。
- `/memory`：真实实时记忆占用、搜索、状态筛选、来源回合与 revision 展示。
- `/skills`：Skill 列表、统计与版本信息骨架。
- `/activity`：后台任务汇总与状态列表。
- `/settings`：持久化 OpenAI 兼容 Base URL、模型、超时和输出上限，并显示当前 Workspace 与可用工具；API Key 仅从环境变量读取。

## 目录

```text
apps/web/             React 图形前端
services/api/         FastAPI 服务
migrations/           Alembic 数据库迁移
packages/contracts/   跨端结构化契约（后续阶段扩展）
tests/backend/        后端测试
tests/e2e/            端到端测试（后续阶段扩展）
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

工具只能访问 `SURVIVAL_AGENT_WORKSPACE_PATH` 配置的 Workspace（默认 `./workspace`）。路径必须为相对路径；写入已有文件必须由模型显式传入 `overwrite=true`。Workspace 内容是本地用户数据，不提交 Git。

Token 生存账本内部使用整数 Units（100 Units = 1 Token）：读取与输出初始余额分别为 1,000,000,000 和 100,000,000 Token。系统不会因余额不足自动拒绝任务，也不会把缓存或推理明细重复计入 Provider 的总 Usage。

实时记忆只对明显长期指令进行确定性检测，不额外调用模型。有效增量最多 2,000 个 Unicode Code Point；重复表达合并占用，溢出内容保留为 `deferred_capacity`，不会静默删除。正式长期记忆与后台整理在第 6 阶段接入。

## 验证

```powershell
npm run lint:web
npm run test:web
npm run build:web
uv run ruff check .
uv run pytest
```

真实密钥只允许保存在本地环境变量或未来桌面端的系统 Keychain 中，不进入数据库或 Git。
