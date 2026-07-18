# Changelog

## 0.3.0 - 2026-07-18

### Added

- 添加会话、消息、回合和三类模型角色的正式 SQLite/Alembic 数据结构。
- 添加会话 CRUD、回合创建/取消/重新生成和模型设置 REST API。
- 添加 OpenAI 兼容 Chat Completions SSE Provider 与结构化 WebSocket 事件。
- 前端接入真实会话列表、流式输出、停止生成、错误重试和刷新恢复。
- 添加 Provider、持久化、取消、缺密钥和流式前端测试。
- 添加 Provider 模型发现 API、非流式兼容回包与安全事件字段诊断。

### Changed

- Provider 优先使用兼容性更广的 `max_tokens`，服务明确拒绝时自动切换 `max_completion_tokens`。
- 完成 `https://api.a6api.com/v1` + `gpt-5.6-sol` 真实流式与持久化验收。

### Security

- API Key 只从 `OPENAI_API_KEY` 环境变量读取，模型设置 API 和数据库均不接收明文密钥。
- Provider 错误不会记录或返回 Authorization Header。

## 0.2.0 - 2026-07-18

### Added

- 实现可折叠的会话栏、对话工作区和 Agent 状态栏三栏布局。
- 添加聊天、记忆、Skill、后台活动和设置五个图形页面。
- 添加 Mock 工具展开、满意/不满意、输入状态、路由与侧栏交互。
- 添加第 1 阶段应用壳单元测试和桌面、移动视觉验收证据。

### Changed

- 将第 0 阶段连接状态页替换为正式产品图形骨架；健康检查能力保留供后续设置与诊断页面接入。

## 0.1.0 - 2026-07-18

### Added

- 建立 Monorepo、React/Vite 前端和 FastAPI 后端。
- 配置 SQLite WAL、SQLAlchemy、Alembic 迁移与 `/api/health`。
- 添加前端连接状态页、重试交互和断线状态。
- 添加 Vitest、pytest、ESLint、Ruff、Prettier 与基础文档。
