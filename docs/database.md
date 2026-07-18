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

## 数据路径

开发默认数据库：`data/survival_agent.db`。路径可通过 `SURVIVAL_AGENT_DATABASE_URL` 覆盖。数据库文件、WAL 和共享内存文件均不提交 Git。
