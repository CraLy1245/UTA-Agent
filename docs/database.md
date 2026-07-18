# 数据库设计

## 基础配置

- SQLite 使用 WAL 模式。
- 每个连接启用 `foreign_keys=ON`。
- `busy_timeout=5000ms`，降低短暂写锁导致的失败。
- 所有 Schema 变更必须由 Alembic migration 完成。
- 时间字段统一保存 UTC；业务表 ID 将统一使用 UUID。

## 第 0 阶段表

`app_metadata` 仅记录数据库初始化信息，用于证明 migration 流程有效。业务表将在对应阶段按领域逐步加入，避免在规则尚未通过测试前冻结错误 Schema。

| 字段       | 类型         | 说明         |
| ---------- | ------------ | ------------ |
| key        | VARCHAR(100) | 主键         |
| value      | TEXT         | 值           |
| updated_at | DATETIME     | UTC 更新时间 |

## 第 2 阶段表

- `conversations`：会话标题与创建/更新时间。
- `messages`：按 `conversation_id + sequence` 读取的用户和助手消息；回合取消或失败时不保存助手半截输出。
- `turns`：pending、running、completed、cancelled、failed 状态，以及错误、Provider usage 和重新生成来源。
- `model_settings`：`main`、`memory`、`skill` 三个可独立演化的模型角色。只保存非敏感配置和 API Key 环境变量名称。

会话删除通过外键级联移除其消息与回合。重新生成回合复用原始用户消息，并通过 `source_turn_id` 保留来源。

## 第 3 阶段表

`tool_executions` 为每次模型工具调用保存：所属会话与回合、Provider 调用 ID、回合内序号、工具名、参数 JSON、pending/completed/failed 状态、结果 JSON、错误和起止时间。`turn_id + provider_call_id` 唯一，避免同一 Provider 调用被重复记账；会话或回合删除时级联清理。

工具记录只保存模型给出的相对路径和结构化结果，不保存 API Key。文件实体位于配置的 Workspace，不进入数据库。

## 第 4 阶段表

- `token_accounts`：`read`、`output` 两个账户的当前与初始 Units 余额。迁移初始值分别为 100,000,000,000 与 10,000,000,000 Units。
- `token_transactions`：每回合两条 `usage_debit` 和首次满意时两条 `survival_reward`。保存前后余额、反馈事件关联、元数据和唯一 `idempotency_key`。会话删除时 `turn_id` 置空而不删除交易，避免余额失去审计依据。
- `feedback_events`：追加保存每次满意/不满意及文字反馈；允许修改评价但完整历史不覆盖。
- `turn_execution_traces`：每个成功回合唯一且创建后不更新，保存独立 Token/状态/时间字段，以及模型、实际 revision ID 数组、工具、raw/normalized Usage 和客观结果 JSON。

迁移只从第 4 阶段开始建立初始账户；早期回合没有 execution trace，也不会被追溯扣款或伪造 raw Usage。只有 `20260718_0004` 之后真实完成的回合进入账本。

## 第 5 阶段表

`memory_delta` 保存显式实时记忆：UUID、不可变 `revision_id`、来源回合 ID、原始/归一化内容、类型、优先级、状态、Unicode 字符数、未来消费 Job ID 和 UTC 创建时间。

当前状态包括：

- `pending`：计入 2,000 字符实时额度并从下一回合开始注入。
- `deferred_capacity`：因容量不足等待第 6 阶段整理，记录仍完整保留。
- `duplicate_merged`：与有效指令重复，保留来源审计但不重复占额。
- `consumed`：为第 6 阶段正式记忆合并预留。

来源回合 ID 以不可变审计值保存，因此用户删除会话时不会级联删除已经形成的记忆。第 6 阶段创建正式记忆与 revision 后，可通过 `consumed_by_job_id` 建立整理链路。

## 第 6 阶段表

- `turns.completed_number`：可空全局唯一序号，只给成功最终提交的完整回合赋值。
- `cognitive_state`：单行保存完成回合总数、最后成功整理回合及当前 memory version。
- `cognitive_jobs`：保存冻结范围、状态、前后版本、尝试次数、下一重试时间、领取/起止时间、错误与结果；`job_type + start_turn_number + end_turn_number` 唯一。
- `memory_items`：稳定记忆 ID、分类、标题、当前内容、标签、优先级、active/archived/superseded、锁定状态、当前 revision 和字符数。
- `memory_revisions`：每次变化的完整不可变快照，含 previous revision、操作、来源回合、Job、创建者与原因。
- `memory_snapshots`：每个 memory version 的生效 revision ID 列表与正式字符总数；认知 Job ID 唯一，用户手工版本允许空 Job。
- `memory_items_fts`：SQLite FTS5 外部内容索引，由 insert/update/delete trigger 与 `memory_items` 保持一致。

正式额度只统计 active `memory_items.char_count`，上限 18,000；实时额度只统计有效 `memory_delta`，上限 2,000。历史 revision、snapshot、archived/superseded item 不计入额度且不会永久删除。`current_revision_id`、`previous_revision_id`、来源 IDs 与 Job IDs 部分采用逻辑审计关联，提交校验负责一致性，避免 SQLite 循环外键阻碍原子版本切换。

## 第 7 阶段表

- `skills`：当前可用视图、锁定/归档状态、使用/满意/失败统计、选择权重、稳定与候选 Revision、回滚保护和观察期。
- `skill_revisions`：保存每次创建、更新、合并、候选、晋升、拒绝、归档和回滚所对应的完整内容、前一 Revision、来源回合、Job、原因、预期改进及唯一幂等键。
- `skill_usage`：以 `turn_id + skill_revision_id` 唯一，保存本轮实际版本、完成状态、最新质量反馈、客观通过及独立 Token 用量。
- `skill_evolution_events`：不可变演化审计，保存 Skill/Revision/Job、事件类型、原因、确定性评估证据和唯一幂等键。

稳定与候选指针是核心独立字段，不藏入 JSON。来源列表和评估证据使用 JSON，但必须通过服务层验证真实 ID、锁定、基础 Revision、阈值与幂等性。归档和拒绝只改变生命周期状态，不删除历史。

## 第 8 阶段一致性与恢复

第 8 阶段不新增业务表或运行时 `create_all()`；现有 `20260718_0007` 仍为 Alembic head。稳定性规则落在事务、状态机和测试边界：

- Worker `BEGIN IMMEDIATE` 领取后立即提交领取状态；同一 Job 不会被两个 Session 同时领取。
- `pending/conflict + next_attempt_at` 是可恢复的 Durable Queue。未来重试不会阻塞后续 ready Job。
- 新进程启动将旧进程未完成的 running/validating/committing 领取恢复为 pending；SQLite 只恢复未完成状态，不改动已提交事务。
- 导出使用只读事务固定 WAL 快照并显式白名单 19 张业务表；密钥字段排除后再递归脱敏。
- `PRAGMA integrity_check`、WAL、Foreign Keys、Busy Timeout、空库 Alembic 和引擎关闭重开均进入自动化验收。

## 数据路径

开发默认数据库：`data/survival_agent.db`。路径可通过 `SURVIVAL_AGENT_DATABASE_URL` 覆盖。数据库文件、WAL 和共享内存文件均不提交 Git。
