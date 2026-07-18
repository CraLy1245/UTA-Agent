# Changelog

## 0.6.0 - 2026-07-18

### Added

- 添加显式长期指令的确定性检测、真实 `memory_delta` SQLite/Alembic 持久化和 `memory.delta_created` 事件。
- 添加每条实时增量的不可变 revision ID，并把本轮实际注入的 revision IDs 写入 execution trace。
- 添加实时记忆状态与列表 API，以及记忆管理页的占用、搜索、状态、来源回合和 revision 展示。
- 右侧状态栏显示实时增量占用与等待整理数量。

### Changed

- 当前回合捕获的新指令不自注入；从因果顺序中的下一回合开始，每轮重新读取有效实时增量。
- 2,000 字符容量使用 Unicode Code Point 计算；重复指令合并占用，优先保留明确纠正，溢出记录保留为 `deferred_capacity`。
- 收紧问句检测，引用既有“以后不要”要求的元问题不会被误写成新记忆。

### Security

- 记忆上下文只保存用户原始显式表达和结构化来源，不保存 API Key、Authorization Header 或完整模型上下文。
- 容量重排与回合创建使用 SQLite 写事务，避免并发捕获突破实时额度。

## 0.5.0 - 2026-07-18

### Added

- 添加读取/输出 Token 账户、整数 Units 交易账本和初始余额 Alembic 数据。
- 添加统一 `UsageNormalizer`，同时保存 Provider 原始 Usage 与归一化 Usage，缓存和推理明细不重复计费。
- 添加每轮原子扣款、满意 108% 精确奖励、不满意与文字反馈、评价历史及幂等键。
- 添加不可变 `turn_execution_traces`，记录模型、真实工具、原始/归一化 Usage、延迟与结构化结果。
- 添加生存状态、交易历史、反馈、执行轨迹 API，以及 `usage.updated`/`balance.updated` 事件。
- 右侧状态栏显示两类余额、本轮消耗和交易历史；回答支持可持久化满意/不满意与文字反馈。

### Changed

- 每轮模型上下文动态注入当前两类余额，但余额不用于拒绝任务或削减必要验证。
- `survival_reward` 与 `quality_feedback` 使用同一反馈事件关联但由独立服务处理，评价修改不会撤销或重复发放奖励。

### Security

- Token、反馈和执行轨迹不保存 API Key、Authorization Header 或完整模型上下文。
- 账本交易使用唯一幂等键；反馈写入使用 SQLite `BEGIN IMMEDIATE` 串行化奖励判断。

## 0.4.0 - 2026-07-18

### Added

- 添加 `list_directory`、`read_file`、`write_file` 三个 Workspace 工具及 OpenAI 兼容结构化工具循环。
- 添加 `tool_executions` SQLite/Alembic 持久化、工具状态 API 和 `tool.started/completed/failed` WebSocket 事件。
- 前端显示实时及刷新恢复后的工具参数、结果、成功和失败状态。
- 添加目录、读写、越界、覆盖保护、Provider 工具增量和多轮工具循环测试。

### Changed

- Provider 在模型请求中发送 JSON Schema 工具定义，并把每个工具结果按原始 `tool_call_id` 回传模型后继续生成。
- 设置页显示实际解析后的 Workspace 路径与可用工具。

### Security

- 拒绝绝对路径、父目录穿越、Windows 驱动器/ADS/保留名和经符号链接或 junction 逃逸 Workspace 的路径。
- 文件写入使用显式覆盖授权、大小限制与同目录原子替换；工具不提供删除、执行命令或网络访问能力。

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
