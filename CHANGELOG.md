# Changelog

## 0.1.0-alpha.1 - 2026-07-19

首次公开的实验性快照。版本号不表示生产就绪；已知限制和未完成验收见 README、ROADMAP 与 `docs/development-status.md`。

### Added

- 添加 Tauri 2 Windows Shell、PyInstaller 6.16.0 `--onedir` FastAPI Sidecar 与 NSIS 当前用户安装包。
- 添加动态本机空闲端口、Sidecar 健康门禁、三次启动重试、一次性本地关闭令牌与 8 秒优雅退出回收。
- 添加 `%APPDATA%/SurvivalAgent/{data,logs,workspace,backups}` 用户目录、启动前 Alembic 自动迁移和启动错误日志。
- 添加 Windows 凭据管理器 API Key 存储；密钥仅以子进程环境传递，不进入命令行、SQLite 或安装资源。
- 添加真实 Sidecar E2E，覆盖空库迁移、未授权关闭拒绝、进程重启和 SQLite 数据保留。

### Changed

- 生产前端在启动时从 Tauri 获取动态 REST/WebSocket 地址，浏览器开发模式继续使用相对 `/api`。
- 空库模型默认配置更新为 `https://api.a6api.com/v1` + `gpt-5.6-sol`，仅迁移原始内置默认值，不覆盖用户自定义配置。
- 设置页在桌面模式显示系统凭据输入与真实 `%APPDATA%` Workspace；状态栏标识第 9 阶段。

### Fixed

- 明确认知整理中 Memory 与 Skill 操作的独立 JSON 字段契约，并提供 Skill 新增与候选版本示例，避免模型把 `category`、`tags`、`priority` 等记忆字段混入 Skill 后反复校验失败。

### Security

- Sidecar 使用 `CREATE_NO_WINDOW`、关闭端点要求随机令牌、CSP 只允许本地 loopback HTTP/WebSocket。
- 安装器不含真实 API Key、代理地址或凭据；公开分发前仍需外部代码签名证书。

## 0.9.0 - 2026-07-19

### Added

- 添加一致 WAL 读快照的 `GET /api/data/export` 与设置页 JSON 下载，覆盖会话、账本、记忆、Job、Skill 和完整版本历史。
- 添加四类轮转日志、统一上下文字段、全局 SQLite busy 安全响应，以及错误/日志/导出递归脱敏。
- 添加独立进程 22 回合 E2E：20 回合触发、21 回合前台并行、22 回合读取新记忆、108% 幂等奖励、导出及重启恢复。
- 添加双 Worker 并发领取、延迟 Job 不阻塞、重启回收、SQLite 完整性和脱敏回归测试。

### Changed

- Cognitive Worker 的 conflict 保持可见且按 10/30 秒自动重新领取；查询直接跳过尚未到期的重试任务，不阻塞其他 ready Job。
- 新进程启动时立即回收上一进程的 `running/validating/committing` 领取，已提交事务与历史版本保持不变。

### Security

- Provider/Worker 错误持久化、WebSocket 错误、日志与导出统一清理当前环境密钥、`sk-` 形态、Authorization Bearer 及常见密钥字段。
- 导出明确排除 `model_settings.api_key_env`，真实浏览器下载经三类凭据模式扫描均为 0 命中。

## 0.8.0 - 2026-07-18

### Added

- 添加真实 `skills`、`skill_revisions`、`skill_usage` 与 `skill_evolution_events` SQLite/Alembic 持久化及审计 API。
- 添加 Skill Registry、最多 3 个/8,000 字符动态检索，并在 execution trace 中保存实际加载 Revision IDs。
- 添加严格 Worker Skill 操作、三次复用阈值、锁定/归档/合并/版本冲突校验与不可变 Revision。
- 添加 Candidate/Stable/Superseded/Rejected 生命周期、确定性 9:1 路由、最少 5 次评估、晋升/拒绝与晋升后自动回滚。
- 添加完整 Skill 管理/演化页面、后台演化链，以及独立结构化 Skill WebSocket 事件。

### Changed

- Cognitive Worker 现在读取 Skill 索引、实际 Skill Revision trace、质量反馈和客观结果；只有确定性验证通过后才提交 Skill 操作。
- 质量反馈按回合准确归因到实际 Skill Revision，评价修改重算统计，不会重复影响 Token 奖励。

### Security

- 候选不得删除稳定版本的 `success_criteria` 或安全约束；锁定 Skill 禁止后台修改或创建候选。
- Skill 表、Revision、事件、契约、日志和测试均不保存 API Key；生存奖励与质量评分继续保持业务分离。

## 0.7.0 - 2026-07-18

### Added

- 添加只在 assistant final 成功事务提交后分配的全局完整回合序号，以及每 20 回合唯一冻结范围的 Durable Cognitive Job。
- 添加与前台解耦的 Cognitive Worker、启动恢复、10/30 秒自动重试、手动重试及 `pending/running/validating/committing/completed/failed/conflict` 状态。
- 添加严格 JSON/Pydantic/ID/锁定/乐观版本/18,000 字符/2,000 字符/原始显式增量保真校验；失败完整保留旧记忆。
- 添加 `memory_items`、不可变 `memory_revisions`、`memory_snapshots`、FTS5 检索、正式记忆动态注入和 consumed Job 链路。
- 添加完整记忆管理与后台活动 API/页面，以及 `cognitive.job_started/completed/failed` 独立 WebSocket 事件。

### Changed

- execution trace 的 `memory_revision_ids` 同时记录本轮实际注入的正式 revision 与仍有效实时 delta revision。
- 记忆页支持搜索、锁定/解锁、编辑接口、归档/恢复、历史与回滚；右侧栏显示正式版本和最近认知批次。

### Security

- Worker 模型只能提出操作，数据库变更由确定性代码在短写事务中校验并提交；模型网络调用期间不持 SQLite 写锁。
- 认知错误持久化前脱敏疑似密钥；API Key 仍只来自环境变量，不写入 Job、trace、数据库或 Git。

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
