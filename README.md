# Survival Agent

Survival Agent 是一个本地运行、图形优先、数据可恢复的 AI Agent。项目采用独立实现，不 Fork Hermes Agent；第一版按阶段交付，先确保基础架构稳定，再逐步加入对话、工具、Token 生存账本、记忆与 Skill 演化。

## 当前状态

第 0、1、2 阶段已完成。前端使用正式 REST/WebSocket API，会话、回合和消息保存在 SQLite，OpenAI 兼容 Provider 支持 SSE 流式输出、停止生成和失败重试。第 2 阶段已使用真实 `gpt-5.6-sol` 完成回答、token 用量记录与刷新持久化验收。

已实现页面：

- `/chat/:conversationId`：创建/切换/重命名/删除会话，流式回答、停止生成、失败重试与刷新恢复。
- `/memory`：记忆筛选、占用、来源与状态骨架。
- `/skills`：Skill 列表、统计与版本信息骨架。
- `/activity`：后台任务汇总与状态列表。
- `/settings`：持久化 OpenAI 兼容 Base URL、模型、超时和输出上限；API Key 仅从环境变量读取。

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

## 验证

```powershell
npm run lint:web
npm run test:web
npm run build:web
uv run ruff check .
uv run pytest
```

真实密钥只允许保存在本地环境变量或未来桌面端的系统 Keychain 中，不进入数据库或 Git。
