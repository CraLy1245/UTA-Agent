# Survival Agent

Survival Agent 是一个本地运行、图形优先、数据可恢复的 AI Agent。项目采用独立实现，不 Fork Hermes Agent；第一版按阶段交付，先确保基础架构稳定，再逐步加入对话、工具、Token 生存账本、记忆与 Skill 演化。

## 当前状态

第 0、1 阶段已完成：基础架构、Hermes 风格三栏图形前端骨架、五个主路由与 Mock 数据交互均已通过验收。当前尚未接入真实模型；第 2 阶段将实现 OpenAI 兼容 Provider、持久化对话和结构化流式事件。

已实现页面：

- `/chat/:conversationId`：三栏对话工作区、工具状态、反馈与输入框 Mock 交互。
- `/memory`：记忆筛选、占用、来源与状态骨架。
- `/skills`：Skill 列表、统计与版本信息骨架。
- `/activity`：后台任务汇总与状态列表。
- `/settings`：模型、本地目录、工具开关与危险操作分区。

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
uv run uvicorn services.api.app.main:app --reload
```

另开一个终端：

```powershell
npm run dev:web
```

访问 `http://localhost:5173`。API 健康检查位于 `http://127.0.0.1:8000/api/health`。

## 验证

```powershell
npm run lint:web
npm run test:web
npm run build:web
uv run ruff check .
uv run pytest
```

真实密钥只允许保存在本地环境变量或未来桌面端的系统 Keychain 中，不进入数据库或 Git。
