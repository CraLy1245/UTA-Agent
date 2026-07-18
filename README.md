# Survival Agent

Survival Agent 是一个本地运行、图形优先、数据可恢复的 AI Agent。项目采用独立实现，不 Fork Hermes Agent；第一版按阶段交付，先确保基础架构稳定，再逐步加入对话、工具、Token 生存账本、记忆与 Skill 演化。

## 当前状态

第 0 阶段已完成：React + TypeScript + Vite 前端、FastAPI 后端、SQLite/SQLAlchemy/Alembic、健康检查、测试与质量工具。尚未接入真实模型或业务功能。

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
