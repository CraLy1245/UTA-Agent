import {
  Check,
  ChevronDown,
  Copy,
  MoreHorizontal,
  Paperclip,
  Send,
  Square,
  ThumbsDown,
  ThumbsUp,
  Wrench,
} from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

export function ChatPage() {
  const { conversationId } = useParams();
  const [draft, setDraft] = useState("");
  const [copied, setCopied] = useState(false);
  const [rating, setRating] = useState<"satisfied" | "unsatisfied" | null>(
    null,
  );
  const [toolOpen, setToolOpen] = useState(false);

  return (
    <section className="chat-page">
      <header className="chat-header">
        <div>
          <h1>{conversationId === "mock-1" ? "产品开发规划" : "模拟对话"}</h1>
          <p>4 条消息 · 本地保存</p>
        </div>
        <button type="button" aria-label="更多对话操作">
          <MoreHorizontal />
        </button>
      </header>

      <div className="message-scroll">
        <div className="message user-message">
          我们先完成第一阶段的前端骨架，保持后续模型层可替换。<time>19:18</time>
        </div>
        <div className="assistant-row">
          <div className="agent-avatar">S</div>
          <div className="assistant-content">
            <div className="message assistant-message">
              <p>
                明白。第一阶段只构建图形界面和 Mock 交互，不提前耦合真实模型。
              </p>
              <p>
                我会保留清晰的组件边界：会话导航、对话工作区、Agent
                状态与独立管理页面分别维护，后续可以逐步接入 API 和结构化事件。
              </p>
              <time>19:19</time>
            </div>
            <button
              className="tool-row"
              type="button"
              onClick={() => setToolOpen((value) => !value)}
              aria-expanded={toolOpen}
            >
              <Wrench size={16} />
              <span>已完成 2 个模拟工具步骤</span>
              <ChevronDown size={16} />
            </button>
            {toolOpen ? (
              <div className="tool-details">读取开发方案 · 检查项目目录</div>
            ) : null}
            <div className="message-actions">
              <button
                type="button"
                onClick={() => {
                  setCopied(true);
                  void navigator.clipboard?.writeText("第一阶段 Mock 回答");
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
      </div>

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="输入消息…（Enter 发送，Shift + Enter 换行）"
            aria-label="消息内容"
          />
          <div className="composer-actions">
            <button type="button" aria-label="添加附件">
              <Paperclip />
            </button>
            <span>{draft.length} / 4000</span>
            <button
              className="send-button"
              type="button"
              disabled={!draft.trim()}
              aria-label="发送消息"
            >
              <Send />
            </button>
            <button type="button" aria-label="停止生成">
              <Square />
            </button>
          </div>
        </div>
        <p>当前为第 1 阶段 Mock 界面，不会发送到真实模型。</p>
      </div>
    </section>
  );
}
