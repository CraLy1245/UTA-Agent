import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  Copy,
  MoreHorizontal,
  Paperclip,
  RotateCcw,
  Send,
  Square,
  ThumbsDown,
  ThumbsUp,
  Wrench,
} from "lucide-react";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { chatApi, turnWebSocketUrl } from "../../services/chat";
import type {
  Message,
  StreamEvent,
  ToolExecution,
  Turn,
} from "../../types/chat";

const toolLabels: Record<string, string> = {
  list_directory: "列出目录",
  read_file: "读取文件",
  write_file: "写入文件",
};

function ToolExecutionCard({ tool }: { tool: ToolExecution }) {
  const statusLabel =
    tool.status === "running"
      ? "执行中"
      : tool.status === "completed"
        ? "已完成"
        : "失败";
  return (
    <details className={`tool-execution ${tool.status}`}>
      <summary>
        <span className="tool-icon">
          <Wrench />
        </span>
        <span>
          <b>{toolLabels[tool.tool_name] ?? tool.tool_name}</b>
          <small>{String(tool.arguments.path ?? "Workspace")}</small>
        </span>
        <em>{statusLabel}</em>
      </summary>
      <div className="tool-execution__body">
        <div>
          <b>参数</b>
          <pre>{JSON.stringify(tool.arguments, null, 2)}</pre>
        </div>
        {tool.result ? (
          <div>
            <b>结果</b>
            <pre>{JSON.stringify(tool.result, null, 2)}</pre>
          </div>
        ) : null}
        {tool.error_message ? <p>{tool.error_message}</p> : null}
      </div>
    </details>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false);
  const [rating, setRating] = useState<"satisfied" | "unsatisfied" | null>(
    null,
  );
  if (message.role === "user") {
    return (
      <div className="message user-message">
        {message.content}
        <time>
          {new Date(message.created_at).toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </time>
      </div>
    );
  }
  return (
    <div className="assistant-row">
      <div className="agent-avatar">S</div>
      <div className="assistant-content">
        <div className="message assistant-message">
          <p>{message.content}</p>
          <time>
            {new Date(message.created_at).toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </time>
        </div>
        <div className="message-actions">
          <button
            type="button"
            onClick={() => {
              setCopied(true);
              void navigator.clipboard?.writeText(message.content);
            }}
            aria-label="复制回答"
          >
            {copied ? <Check /> : <Copy />}
            <span>{copied ? "已复制" : "复制"}</span>
          </button>
          <button
            className={rating === "satisfied" ? "active" : ""}
            type="button"
            onClick={() => setRating("satisfied")}
          >
            <ThumbsUp />
            <span>满意</span>
          </button>
          <button
            className={rating === "unsatisfied" ? "active danger" : ""}
            type="button"
            onClick={() => setRating("unsatisfied")}
          >
            <ThumbsDown />
            <span>不满意</span>
          </button>
        </div>
      </div>
    </div>
  );
}

export function ChatPage() {
  const { conversationId = "new" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);
  const streamConversationRef = useRef<string | null>(null);
  const [draft, setDraft] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [activeTurn, setActiveTurn] = useState<Turn | null>(null);
  const [activeTools, setActiveTools] = useState<ToolExecution[]>([]);
  const [error, setError] = useState<string | null>(null);
  const detail = useQuery({
    queryKey: ["conversation", conversationId],
    queryFn: () => chatApi.getConversation(conversationId),
    enabled: conversationId !== "new",
  });

  useEffect(() => {
    if (
      streamConversationRef.current &&
      streamConversationRef.current !== conversationId
    ) {
      socketRef.current?.close();
      socketRef.current = null;
      streamConversationRef.current = null;
      setActiveTurn(null);
      setStreamingContent("");
      setActiveTools([]);
    }
  }, [conversationId]);

  const finishStream = useCallback(
    (targetConversationId: string) => {
      socketRef.current?.close();
      socketRef.current = null;
      streamConversationRef.current = null;
      setActiveTurn(null);
      setStreamingContent("");
      setActiveTools([]);
      void queryClient.invalidateQueries({
        queryKey: ["conversation", targetConversationId],
      });
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    [queryClient],
  );

  const startStreaming = useCallback(
    (turn: Turn) => {
      setActiveTurn(turn);
      streamConversationRef.current = turn.conversation_id;
      setStreamingContent("");
      setActiveTools([]);
      setError(null);
      const socket = new WebSocket(turnWebSocketUrl(turn.id));
      socketRef.current = socket;
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data as string) as StreamEvent;
        if (event.event === "assistant.delta" && event.data.content)
          setStreamingContent((current) => current + event.data.content);
        if (event.event.startsWith("tool.") && event.data.tool) {
          const nextTool = event.data.tool;
          setActiveTools((current) => {
            const existing = current.findIndex(
              (tool) => tool.id === nextTool.id,
            );
            if (existing === -1) return [...current, nextTool];
            return current.map((tool, index) =>
              index === existing ? nextTool : tool,
            );
          });
        }
        if (
          event.event === "assistant.completed" ||
          event.event === "assistant.cancelled"
        )
          finishStream(turn.conversation_id);
        if (event.event === "error") {
          setError(
            typeof event.data.message === "string"
              ? event.data.message
              : "模型请求失败",
          );
          socket.close();
          socketRef.current = null;
          setActiveTurn((current) =>
            current ? { ...current, status: "failed" } : current,
          );
        }
      };
      socket.onerror = () =>
        setError("无法连接本地流式服务，请确认后端正在运行。");
    },
    [finishStream],
  );

  async function handleSend() {
    const content = draft.trim();
    if (!content || activeTurn) return;
    setDraft("");
    try {
      let targetId = conversationId;
      if (targetId === "new") {
        const conversation = await chatApi.createConversation();
        targetId = conversation.id;
        navigate(`/chat/${targetId}`, { replace: true });
        await queryClient.invalidateQueries({ queryKey: ["conversations"] });
      }
      const turn = await chatApi.createTurn(targetId, content);
      await queryClient.invalidateQueries({
        queryKey: ["conversation", targetId],
      });
      startStreaming(turn);
    } catch (cause) {
      setDraft(content);
      setError(cause instanceof Error ? cause.message : "无法发送消息");
    }
  }

  async function handleStop() {
    if (!activeTurn) return;
    await chatApi.cancelTurn(activeTurn.id);
  }

  async function handleRetry() {
    if (!activeTurn) return;
    const turn = await chatApi.regenerateTurn(activeTurn.id);
    startStreaming(turn);
  }

  const messages = detail.data?.messages ?? [];
  return (
    <section className="chat-page">
      <header className="chat-header">
        <div>
          <h1>{detail.data?.title ?? "新对话"}</h1>
          <p>{messages.length} 条消息 · SQLite 本地保存</p>
        </div>
        <button type="button" aria-label="更多对话操作">
          <MoreHorizontal />
        </button>
      </header>
      <div className="message-scroll">
        {conversationId === "new" ||
        (!detail.isLoading && messages.length === 0) ? (
          <div className="chat-empty">
            <div className="agent-avatar">S</div>
            <h2>今天想完成什么？</h2>
            <p>
              消息将保存到本地数据库，并通过你配置的 OpenAI 兼容模型流式回答。
            </p>
          </div>
        ) : null}
        {detail.isError ? (
          <div className="chat-error">
            <AlertCircle />
            {detail.error.message}
          </div>
        ) : null}
        {messages.map((message) => (
          <Fragment key={message.id}>
            <MessageBubble message={message} />
            {message.role === "user"
              ? (detail.data?.tool_executions ?? [])
                  .filter((tool) => tool.turn_id === message.turn_id)
                  .map((tool) => (
                    <ToolExecutionCard key={tool.id} tool={tool} />
                  ))
              : null}
          </Fragment>
        ))}
        {activeTools.map((tool) => (
          <ToolExecutionCard key={tool.id} tool={tool} />
        ))}
        {activeTurn && streamingContent ? (
          <div className="assistant-row">
            <div className="agent-avatar">S</div>
            <div className="assistant-content">
              <div className="message assistant-message streaming-message">
                <p>{streamingContent}</p>
                <span className="stream-cursor" />
              </div>
            </div>
          </div>
        ) : null}
        {error ? (
          <div className="chat-error">
            <AlertCircle />
            <span>{error}</span>
            {activeTurn?.status === "failed" ? (
              <button type="button" onClick={() => void handleRetry()}>
                <RotateCcw />
                重试
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className="composer-wrap">
        <div className="composer">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void handleSend();
              }
            }}
            placeholder="输入消息…（Enter 发送，Shift + Enter 换行）"
            aria-label="消息内容"
            disabled={Boolean(activeTurn)}
          />
          <div className="composer-actions">
            <button
              type="button"
              aria-label="添加附件"
              disabled
              title="第 3 阶段接入"
            >
              <Paperclip />
            </button>
            <span>{draft.length} / 40000</span>
            {activeTurn ? (
              <button
                className="stop-button"
                type="button"
                onClick={() => void handleStop()}
                aria-label="停止生成"
              >
                <Square />
              </button>
            ) : (
              <button
                className="send-button"
                type="button"
                disabled={!draft.trim()}
                onClick={() => void handleSend()}
                aria-label="发送消息"
              >
                <Send />
              </button>
            )}
          </div>
        </div>
        <p>
          {activeTurn
            ? "正在通过本地 WebSocket 接收模型输出…"
            : "回答可能有误，请核对重要信息。"}
        </p>
      </div>
    </section>
  );
}
