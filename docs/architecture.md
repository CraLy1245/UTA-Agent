# 系统架构

## 原则

Survival Agent 采用本地优先、图形优先、可审计和可恢复的模块化架构。前端不直接访问数据库；FastAPI 是一致性边界；后台 Worker 在后续阶段通过 durable job 与前台解耦。

```text
React/Vite UI
    │ REST + WebSocket
FastAPI API
    ├─ Conversation API ─ SQLAlchemy transaction boundary
    └─ Turn Runtime ─ OpenAI-compatible SSE Provider
                    └─ Workspace Tool Runtime
    └─ Survival API ─ Quality Feedback + Reward Service
SQLite WAL
    │ cognitive_jobs + versioned memory
Cognitive Worker ─ strict JSON proposal ─ deterministic commit validator
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

## 第 3 阶段工具边界

- 主模型通过结构化 `tool_calls` 选择列目录、读文件或写文件；运行时执行后将结构化结果返回同一模型，直至得到最终回答。
- 每次调用先写入 `tool_executions`，随后持久化 completed 或 failed 结果；页面刷新后仍可审计。
- 工具根目录由 `SURVIVAL_AGENT_WORKSPACE_PATH` 配置并在启动后解析为绝对路径。所有模型输入路径必须是 Workspace 内相对路径，解析后的父目录也必须仍位于根目录。
- 写入采用同目录临时文件与原子替换；覆盖已有文件必须显式授权。当前没有删除、Shell、进程或网络工具。
- 工具失败作为结构化结果回传模型，由模型解释；不会把越界路径变成后端未处理异常。

## 第 4 阶段生存账本与执行轨迹边界

- `UsageNormalizer` 是 Provider Usage 到账本的唯一归一化入口。只累计 `prompt/input_tokens` 与 `completion/output_tokens` 总量，缓存、推理等明细保留在 raw usage 中但不再次扣款。
- 成功最终回合在一个 SQLite 事务中保存 assistant 消息、completed 回合、两条 usage debit、不可变 execution trace 和最新账户余额；取消或失败回合不扣款、不生成 trace。
- 账本使用整数 Units，余额允许低于零且不会触发自动拒绝。每轮开始时动态注入当前余额，并明确质量、真实性和必要验证优先于 Token 效率。
- `quality_feedback` 负责评价、文字和历史；`survival_reward` 只依据 execution trace 发放 108% Token。两个通道由 feedback event ID 关联，代码与契约分离。
- 奖励键 `reward:{turn_id}:{account_type}` 唯一。评价修改保留历史，已发奖励不撤销，重复满意不增加余额。
- execution trace 只在成功最终回答后创建；第 4 阶段记录真实模型、工具、Usage、延迟和客观工具摘要，不提前实现记忆或 Skill 竞争。

## 第 5 阶段实时记忆边界

- 回合创建事务使用确定性短语和纠正语义检测明显长期指令，不额外调用模型；引用既有要求的元问句不会被当作新指令。
- `memory_delta` 立即保存用户原始表达、来源回合、优先级、字符数和不可变 revision ID。当前回合排除自己的增量，下一回合按创建因果顺序重新读取全部有效增量。
- Memory Context 是独立动态 system message，不重建固定工具或生存提示。execution trace 只记录实际放入本轮上下文的 revision IDs。
- 实时有效内容上限为 2,000 Unicode Code Point。重复表达保留审计记录但不重复占额；容量不足时优先保留近期明确纠正，其他记录标记 `deferred_capacity` 而不删除。
- 第 5 阶段不创建正式长期记忆、Revision/Snapshot、20 回合 Job 或 Worker；这些由第 6 阶段消费实时增量后实现。

## 第 6 阶段认知整理边界

- assistant final、消息、账本与 trace 在同一短写事务成功后，才递增 `completed_number`；取消、失败、工具事件、反馈和后台任务不计数。
- `cognitive_jobs` 冻结连续 20 回合范围并以 `job_type + start + end` 唯一。Worker 领取后立即释放写锁，再读取完整批次、trace、质量反馈、正式记忆和实时增量调用后台模型。
- 后台模型仅返回严格 JSON 操作建议。Pydantic 结构、真实 ID、来源回合、锁定项、expected revision、显式增量逐字保真、18,000/2,000 字符预算均由确定性代码验证。
- `memory_items` 使用稳定 ID；每次 add/update/merge/archive/restore/rollback 都产生不可变 revision。成功批次在同一事务提交 snapshot、memory version、consumed delta 和 Job 完成状态。
- 前台不等待 Worker。第 21 回合可继续读取旧正式记忆与有效增量；Worker 提交后，下一回合动态读取新正式 revision。用户并发编辑通过 `current_revision_id` 触发 conflict，Worker 不覆盖用户版本。
- 正式检索优先核心/锁定/高优先级 4,000 字符，再以 SQLite FTS5 选择相关 6,000 字符，实时增量最多 2,000 字符；execution trace 保存实际注入 revision IDs。
- 本阶段 `skill_index` 和 `skill_operations` 必须为空，不实现第 7 阶段 Skill 演化。

## 长期可替换性

- Provider 通过 `ProviderConfig` 和流式事件接口接入，避免绑定单一模型供应商。
- 数据库变更全部通过 Alembic，禁止运行时 `create_all()`。
- 前后端通过结构化契约通信，不解析自然语言推断运行状态。
- Tauri 与 Python sidecar 延后到第 9 阶段，避免打包约束污染核心模块。
