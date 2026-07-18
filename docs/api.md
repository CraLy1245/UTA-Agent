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

生存状态以 Units 返回余额与最近一个真实 execution trace 的本轮用量，`100 Units = 1 Token`。交易金额扣款为负、奖励为正。执行轨迹包含 Provider 原始 Usage、归一化 Usage、模型名、真实工具名、延迟和结构化结果；当前阶段的 memory/skill revision ID 数组为空，后续阶段只填实际注入版本。

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

对话发送 `turn.started`、`assistant.delta`、`usage.updated`、`balance.updated`、`assistant.completed`、`assistant.cancelled` 和 `error`。第 3 阶段另发送 `tool.started`、`tool.completed`、`tool.failed`；事件包含持久化执行 ID、工具调用 ID、序号、工具名、参数，以及完成后的结构化结果或错误。`usage.updated` 同时携带归一化字段与 Provider 原始 Usage，`balance.updated` 在扣款事务提交后携带账户余额和本轮 Units 变化。反馈通过 REST 返回同样的结构化分离结果。前端不得解析自然语言推断运行状态。

## Provider

当前 Provider 调用 `{base_url}/chat/completions`，使用 Chat Completions SSE 格式；Base URL 需要包含服务要求的版本路径（常见为 `/v1`）。优先发送 `max_tokens`；若兼容服务明确报告不支持该字段，则切换 `max_completion_tokens`。Provider 兼容 SSE delta、普通 Chat Completion 回包和分段文本。响应直到完整结束才作为 assistant 消息提交。

工具请求使用 Chat Completions 的 `tools` JSON Schema。运行时按 `index` 合并流式 `delta.tool_calls`，保存 assistant 工具调用，执行本地受限工具，再以 `role=tool` 和原始 `tool_call_id` 回传结果。只有模型结束工具循环并返回最终文本后，才保存 assistant 消息。
