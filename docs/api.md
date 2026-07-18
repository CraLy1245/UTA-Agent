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

第 2 阶段发送 `turn.started`、`assistant.delta`、`usage.updated`、`assistant.completed`、`assistant.cancelled` 和 `error`。前端不得解析自然语言推断运行状态。

## Provider

当前 Provider 调用 `{base_url}/chat/completions`，使用 Chat Completions SSE 格式；Base URL 需要包含服务要求的版本路径（常见为 `/v1`）。优先发送 `max_tokens`；若兼容服务明确报告不支持该字段，则切换 `max_completion_tokens`。Provider 兼容 SSE delta、普通 Chat Completion 回包和分段文本。响应直到完整结束才作为 assistant 消息提交。
