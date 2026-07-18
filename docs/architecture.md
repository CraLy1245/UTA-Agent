# 系统架构

## 原则

Survival Agent 采用本地优先、图形优先、可审计和可恢复的模块化架构。前端不直接访问数据库；FastAPI 是一致性边界；后台 Worker 在后续阶段通过 durable job 与前台解耦。

```text
React/Vite UI
    │ REST + WebSocket（第 2 阶段启用）
FastAPI API
    │ SQLAlchemy transaction boundary
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

## 第 0 阶段边界

当前只实现启动、数据库连接和健康状态。不会提前添加内存 Mock 业务、模型占位调用或不可迁移的数据表。这样能让第 1 阶段专注 UI，第 2 阶段开始接入真实持久化对话。

## 长期可替换性

- Provider 通过统一协议接入，避免绑定单一模型供应商。
- 数据库变更全部通过 Alembic，禁止运行时 `create_all()`。
- 前后端通过结构化契约通信，不解析自然语言推断运行状态。
- Tauri 与 Python sidecar 延后到第 9 阶段，避免打包约束污染核心模块。
