# 系统架构

## 原则

Survival Agent 采用本地优先、图形优先、可审计和可恢复的模块化架构。前端不直接访问数据库；FastAPI 是一致性边界；后台 Worker 在后续阶段通过 durable job 与前台解耦。

```text
React/Vite UI
    │ REST + WebSocket
FastAPI API
    ├─ Conversation API ─ SQLAlchemy transaction boundary
    └─ Turn Runtime ─ OpenAI-compatible SSE Provider
SQLite WAL
    │ durable jobs（第 6 阶段启用）
Cognitive Worker
```

## Monorepo 边界

- `apps/web`：只负责图形交互、查询缓存和客户端状态。
- `services/api`：HTTP/WebSocket 入口、配置、数据库依赖。
- `services/agent`：后续容纳模型循环，不与 API 路由耦合。
- `services/memory`、`services/skills`、`services/survival`：后续各自拥有领域规则。
- `services/worker`：后续独立领取并执行 durable job。
- `packages/contracts`：跨进程结构化事件与操作 Schema。

## 第 2 阶段真实对话边界

- REST API 创建持久化会话、用户消息和 pending 回合。
- WebSocket 连接领取单个 pending 回合，Provider 将上游 SSE 转换为结构化事件。
- 只有收到完整最终回答后才写入 assistant 消息并把回合标为 completed。
- 取消和失败回合不写入半截 assistant 消息；错误状态持久化，可重新生成。
- 当前进程中的取消注册表只传递短暂中断信号，业务真相仍以 SQLite 为准。
- 模型 Base URL、模型名和调用限制写入 `model_settings`；API Key 只来自进程环境。

## 长期可替换性

- Provider 通过 `ProviderConfig` 和流式事件接口接入，避免绑定单一模型供应商。
- 数据库变更全部通过 Alembic，禁止运行时 `create_all()`。
- 前后端通过结构化契约通信，不解析自然语言推断运行状态。
- Tauri 与 Python sidecar 延后到第 9 阶段，避免打包约束污染核心模块。
