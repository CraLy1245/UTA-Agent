# API 与流式事件

## 会话与回合

- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{id}`
- `PATCH /api/conversations/{id}`
- `DELETE /api/conversations/{id}`
- `POST /api/conversations/{id}/turns`
- `GET /api/turns/{id}`
- `POST /api/turns/{id}/cancel`
- `POST /api/turns/{id}/regenerate`

创建回合只持久化用户消息和 pending 回合。前端随后连接 `WS /api/ws/turns/{turnId}` 才开始模型调用，避免 HTTP 请求生命周期承载长流式任务。

## 模型配置

- `GET /api/model-settings/{role}`
- `PUT /api/model-settings/{role}`
- `GET /api/model-settings/{role}/models`

配置支持 `main`、`memory`、`skill` 角色。请求和响应不包含 API Key；`has_api_key` 只表示当前进程是否读取到 `OPENAI_API_KEY`。

## 工具状态

- `GET /api/tools/status`

返回工具是否启用、解析后的 Workspace 路径和可用工具名。它不读取或返回 Workspace 文件内容。

## Token 生存账本与反馈

- `GET /api/survival/status?conversation_id={id}`
- `GET /api/survival/transactions?limit=50&offset=0`
- `POST /api/turns/{id}/feedback`
- `GET /api/turns/{id}/execution-trace`

反馈请求的 `rating` 为 `satisfied` 或 `unsatisfied`，`comment` 可选且最多 2,000 字符。响应明确拆分为 `quality_feedback` 和 `survival_reward`：前者每次都追加历史事件，后者只在首次满意时返回两条奖励交易。评价可以修改，但奖励不撤销，也不会因重复满意再次发放。

生存状态以 Units 返回余额与最近一个真实 execution trace 的本轮用量，`100 Units = 1 Token`。交易金额扣款为负、奖励为正。执行轨迹包含 Provider 原始 Usage、归一化 Usage、模型名、真实工具名、延迟和结构化结果；memory/skill revision 数组只填本轮实际注入的版本。

## Skill Registry 与演化

- `GET/POST /api/skills`
- `GET/PATCH /api/skills/{id}`
- `POST /api/skills/{id}/lock|unlock|archive|restore`
- `GET /api/skills/{id}/revisions`
- `GET /api/skills/{id}/evolution`
- `GET /api/skills/evolution-events`
- `POST /api/skills/{id}/candidate/{revisionId}/promote|reject|pause`
- `POST /api/skills/{id}/rollback/{revisionId}`

编辑必须提交当前稳定 Revision；冲突返回 409。候选操作必须匹配当前 candidate 指针。演化响应同时返回 Skill、不可变 Revision、实际 usage 与审计事件，便于前端显示同期满意率、Token 均值、客观通过和来源链。

## 记忆与认知 Job

- `GET /api/memory?status={status}&query={text}`
- `GET /api/memory/status`
- `GET /api/memory/items?status={status}&category={category}&query={text}`
- `POST /api/memory/items`
- `PATCH /api/memory/items/{id}`（必须提交 `expected_revision_id`）
- `POST /api/memory/items/{id}/lock|unlock|archive|restore`
- `GET /api/memory/items/{id}/revisions`
- `POST /api/memory/items/{id}/rollback/{revisionId}`
- `GET /api/cognitive-jobs`
- `GET /api/cognitive-jobs/{id}`
- `POST /api/cognitive-jobs/{id}/retry`
- `POST /api/cognitive-jobs/run`（本地调试，只领取一个已存在 Job）

实时列表返回用户原始显式表达、来源回合、revision ID、优先级、状态、字符数与 consumed Job。正式记忆接口返回稳定 item ID、当前 revision、锁定/状态和字符数；历史与归档从不永久删除。状态接口返回正式 18,000、实时 2,000 的实际占用与当前 memory version。

## WebSocket

统一信封：

```json
{
  "event": "assistant.delta",
  "conversation_id": "uuid",
  "turn_id": "uuid",
  "timestamp": "2026-07-18T11:00:00+00:00",
  "data": {}
}
```

对话发送 `turn.started`、`assistant.delta`、`usage.updated`、`balance.updated`、`assistant.completed`、`assistant.cancelled` 和 `error`。第 3 阶段另发送 `tool.started`、`tool.completed`、`tool.failed`；第 5 阶段在当前用户消息形成显式增量时发送 `memory.delta_created`，只携带结构化 ID、revision、来源、优先级、状态和字符数，不回显完整记忆。`usage.updated` 同时携带归一化字段与 Provider 原始 Usage，`balance.updated` 在扣款事务提交后携带账户余额和本轮 Units 变化。反馈通过 REST 返回同样的结构化分离结果。前端不得解析自然语言推断运行状态。

独立 `WS /api/ws/cognitive-jobs` 发送 `cognitive.job_started`、`cognitive.job_completed`、`cognitive.job_failed`，信封包含 `job_id`、时间戳及结构化状态/范围/尝试次数/错误/版本，不伪造 conversation 或 turn ID。

独立 `WS /api/ws/skill-events` 发送 Skill 创建/更新/锁定/归档及 `skill.candidate_created|started|evaluated|promoted|rejected|auto_rollback`。信封包含真实 `skill_id`、`revision_id`、`job_id`、原因和确定性证据；前端不解析自然语言判断候选状态。

## Provider

当前 Provider 调用 `{base_url}/chat/completions`，使用 Chat Completions SSE 格式；Base URL 需要包含服务要求的版本路径（常见为 `/v1`）。优先发送 `max_tokens`；若兼容服务明确报告不支持该字段，则切换 `max_completion_tokens`。Provider 兼容 SSE delta、普通 Chat Completion 回包和分段文本。响应直到完整结束才作为 assistant 消息提交。

工具请求使用 Chat Completions 的 `tools` JSON Schema。运行时按 `index` 合并流式 `delta.tool_calls`，保存 assistant 工具调用，执行本地受限工具，再以 `role=tool` 和原始 `tool_call_id` 回传结果。只有模型结束工具循环并返回最终文本后，才保存 assistant 消息。

## 数据导出与并发错误

- `GET /api/data/export`

返回 `application/json` 附件，顶层包含格式版本、UTC 导出时间、数据库类型和 19 个业务表的同一 WAL 读快照。字符串与嵌套 JSON 会清理当前进程密钥、Bearer Header、`sk-` 形态和常见 secret/token/key 字段；`model_settings.api_key_env` 不导出。

SQLite 写锁超过 Busy Timeout 时 API 返回 `503`、安全的 `detail` 与 `Retry-After: 1`；不返回 SQL、路径、Header 或原始异常。记忆/Skill expected revision 冲突仍返回 `409`，由用户刷新后重试。
