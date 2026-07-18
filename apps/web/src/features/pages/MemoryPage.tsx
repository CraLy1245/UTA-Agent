import { useQuery } from "@tanstack/react-query";
import { Brain, Clock3, Search, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { chatApi } from "../../services/chat";
import { PageScaffold } from "./PageScaffold";

const statusLabels: Record<string, string> = {
  pending: "下一回合生效",
  deferred_capacity: "等待整理",
  duplicate_merged: "已合并重复",
  consumed: "已整理",
};

export function MemoryPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const memoryStatus = useQuery({
    queryKey: ["memory-status"],
    queryFn: chatApi.getMemoryStatus,
  });
  const deltas = useQuery({
    queryKey: ["memory-delta", status, search],
    queryFn: () =>
      chatApi.getMemoryDelta(status || undefined, search || undefined),
  });
  const usage = memoryStatus.data;
  const usagePercent = usage
    ? Math.min(
        100,
        (usage.active_delta_char_count / usage.delta_char_limit) * 100,
      )
    : 0;

  return (
    <PageScaffold
      title="记忆"
      description="管理明确要求形成的实时记忆；正式长期记忆将在第 6 阶段接入。"
      icon={Brain}
    >
      <section className="memory-overview" aria-label="记忆占用">
        <article>
          <span>
            <ShieldCheck /> 实时增量
          </span>
          <strong>
            {usage?.active_delta_char_count ?? 0} /{" "}
            {usage?.delta_char_limit ?? 2_000}
          </strong>
          <div className="progress-track">
            <i style={{ width: `${usagePercent}%` }} />
          </div>
          <small>{usage?.pending_count ?? 0} 条有效指令</small>
        </article>
        <article>
          <span>
            <Clock3 /> 容量队列
          </span>
          <strong>{usage?.deferred_count ?? 0} 条</strong>
          <p>超出额度的内容会保留，等待第 6 阶段紧急整理，不会静默删除。</p>
        </article>
      </section>

      <div className="page-toolbar">
        <label>
          <Search />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索实时记忆"
          />
        </label>
        <select
          aria-label="记忆状态"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="">全部状态</option>
          <option value="pending">下一回合生效</option>
          <option value="deferred_capacity">等待整理</option>
          <option value="duplicate_merged">已合并重复</option>
          <option value="consumed">已整理</option>
        </select>
        <span>{deltas.data?.length ?? 0} 条记录</span>
      </div>
      <div className="data-list memory-list">
        {deltas.data?.map((delta) => (
          <article key={delta.id}>
            <div>
              <b>显式指令</b>
              <span className={delta.status}>{statusLabels[delta.status]}</span>
              <em>优先级 {delta.priority}</em>
            </div>
            <p>{delta.raw_content}</p>
            <small>
              {delta.char_count} 字符 · 来源回合{" "}
              {delta.source_turn_id.slice(0, 8)} · revision{" "}
              {delta.revision_id.slice(0, 8)}
            </small>
          </article>
        ))}
        {deltas.isLoading ? <p className="empty-state">正在读取记忆…</p> : null}
        {deltas.isError ? (
          <p className="empty-state error">
            记忆读取失败，请确认后端已完成迁移。
          </p>
        ) : null}
        {!deltas.isLoading && !deltas.isError && !deltas.data?.length ? (
          <p className="empty-state">还没有显式实时记忆。</p>
        ) : null}
      </div>
    </PageScaffold>
  );
}
