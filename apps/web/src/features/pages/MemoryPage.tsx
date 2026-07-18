import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  Brain,
  Clock3,
  History,
  Lock,
  Pencil,
  RotateCcw,
  Search,
  ShieldCheck,
  Unlock,
} from "lucide-react";
import { useState } from "react";

import { chatApi } from "../../services/chat";
import type { MemoryItem } from "../../types/chat";
import { PageScaffold } from "./PageScaffold";

const deltaLabels: Record<string, string> = {
  pending: "下一回合生效",
  deferred_capacity: "等待整理",
  duplicate_merged: "已合并重复",
  consumed: "已整理",
};

export function MemoryPage() {
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("active");
  const [selected, setSelected] = useState<MemoryItem | null>(null);
  const [editing, setEditing] = useState<MemoryItem | null>(null);
  const [editContent, setEditContent] = useState("");
  const usage = useQuery({
    queryKey: ["memory-status"],
    queryFn: chatApi.getMemoryStatus,
  });
  const items = useQuery({
    queryKey: ["memory-items", status, search],
    queryFn: () =>
      chatApi.getMemoryItems(status || undefined, search || undefined),
  });
  const deltas = useQuery({
    queryKey: ["memory-delta"],
    queryFn: () => chatApi.getMemoryDelta(),
  });
  const revisions = useQuery({
    queryKey: ["memory-revisions", selected?.id],
    queryFn: () => chatApi.getMemoryRevisions(selected!.id),
    enabled: Boolean(selected),
  });
  const refresh = () => {
    client.invalidateQueries({ queryKey: ["memory-items"] });
    client.invalidateQueries({ queryKey: ["memory-status"] });
    client.invalidateQueries({ queryKey: ["memory-revisions"] });
  };
  const action = useMutation({
    mutationFn: ({
      item,
      name,
    }: {
      item: MemoryItem;
      name: "lock" | "unlock" | "archive" | "restore";
    }) => chatApi.memoryAction(item.id, name),
    onSuccess: refresh,
  });
  const rollback = useMutation({
    mutationFn: ({ item, revision }: { item: MemoryItem; revision: string }) =>
      chatApi.rollbackMemory(item.id, revision),
    onSuccess: refresh,
  });
  const edit = useMutation({
    mutationFn: () => chatApi.updateMemoryItem(editing!, editContent),
    onSuccess: () => {
      setEditing(null);
      refresh();
    },
  });
  const data = usage.data;

  return (
    <PageScaffold
      title="记忆"
      description="正式记忆按版本长期保留；实时增量在认知整理成功后才标记为已整理。"
      icon={Brain}
    >
      <section className="memory-overview" aria-label="记忆占用">
        <article>
          <span>
            <ShieldCheck /> 正式记忆 · v{data?.current_memory_version ?? 0}
          </span>
          <strong>
            {data?.formal_memory_char_count ?? 0} /{" "}
            {data?.formal_memory_char_limit ?? 18_000}
          </strong>
          <div className="progress-track">
            <i
              style={{
                width: `${Math.min(100, ((data?.formal_memory_char_count ?? 0) / 18_000) * 100)}%`,
              }}
            />
          </div>
          <small>历史版本与归档内容不占额度</small>
        </article>
        <article>
          <span>
            <Clock3 /> 实时增量
          </span>
          <strong>
            {data?.active_delta_char_count ?? 0} /{" "}
            {data?.delta_char_limit ?? 2_000}
          </strong>
          <p>
            {data?.pending_count ?? 0} 条有效，{data?.deferred_count ?? 0}{" "}
            条等待整理
          </p>
        </article>
      </section>
      <div className="page-toolbar">
        <label>
          <Search />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索正式记忆"
          />
        </label>
        <select
          aria-label="正式记忆状态"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="active">生效中</option>
          <option value="archived">已归档</option>
          <option value="superseded">已合并</option>
          <option value="">全部</option>
        </select>
        <span>{items.data?.length ?? 0} 条正式记忆</span>
      </div>
      <div className="data-list memory-list">
        {items.data?.map((item) => (
          <article key={item.id}>
            <div>
              <b>{item.title}</b>
              <span>{item.category}</span>
              {item.locked ? <span>已锁定</span> : null}
              <em>优先级 {item.priority}</em>
            </div>
            <p>{item.content}</p>
            <small>
              {item.char_count} 字符 · revision{" "}
              {item.current_revision_id.slice(0, 8)}
            </small>
            <div className="memory-actions">
              <button
                onClick={() => {
                  setEditing(item);
                  setEditContent(item.content);
                }}
              >
                <Pencil /> 编辑
              </button>
              <button
                onClick={() =>
                  action.mutate({
                    item,
                    name: item.locked ? "unlock" : "lock",
                  })
                }
              >
                {item.locked ? <Unlock /> : <Lock />}
                {item.locked ? "解锁" : "锁定"}
              </button>
              <button
                onClick={() =>
                  action.mutate({
                    item,
                    name: item.status === "active" ? "archive" : "restore",
                  })
                }
              >
                <Archive /> {item.status === "active" ? "归档" : "恢复"}
              </button>
              <button onClick={() => setSelected(item)}>
                <History /> 版本历史
              </button>
            </div>
          </article>
        ))}
        {!items.isLoading && !items.data?.length ? (
          <p className="empty-state">
            还没有正式记忆；第一个完整 20 回合批次会触发整理。
          </p>
        ) : null}
      </div>
      {editing ? (
        <section className="memory-editor">
          <header>
            <b>编辑：{editing.title}</b>
            <span>{editContent.length} / 18000</span>
          </header>
          <textarea
            aria-label="正式记忆内容"
            value={editContent}
            maxLength={18_000}
            onChange={(event) => setEditContent(event.target.value)}
          />
          <div>
            <button onClick={() => setEditing(null)}>取消</button>
            <button
              className="primary-button"
              disabled={!editContent.trim() || edit.isPending}
              onClick={() => edit.mutate()}
            >
              保存新版本
            </button>
          </div>
          {edit.isError ? (
            <p className="error">
              保存失败：{edit.error.message}。输入已保留，请刷新确认当前版本。
            </p>
          ) : null}
        </section>
      ) : null}
      {selected ? (
        <section className="revision-panel">
          <header>
            <div>
              <History />
              <b>{selected.title} · 版本历史</b>
            </div>
            <button onClick={() => setSelected(null)}>关闭</button>
          </header>
          {revisions.data?.map((revision) => (
            <article key={revision.id}>
              <div>
                <b>{revision.operation}</b>
                <span>
                  {new Date(revision.created_at).toLocaleString("zh-CN")}
                </span>
              </div>
              <p>{revision.content}</p>
              <small>
                {revision.created_by} · {revision.reason ?? "无说明"}
              </small>
              {revision.id !== selected.current_revision_id ? (
                <button
                  onClick={() =>
                    rollback.mutate({ item: selected, revision: revision.id })
                  }
                >
                  <RotateCcw /> 回滚到此版本
                </button>
              ) : (
                <em>当前版本</em>
              )}
            </article>
          ))}
        </section>
      ) : null}
      <h2 className="section-heading">实时增量与 consumed 链路</h2>
      <div className="data-list memory-list">
        {deltas.data?.map((delta) => (
          <article key={delta.id}>
            <div>
              <b>显式指令</b>
              <span className={delta.status}>{deltaLabels[delta.status]}</span>
            </div>
            <p>{delta.raw_content}</p>
            <small>
              {delta.char_count} 字符 · 来源 {delta.source_turn_id.slice(0, 8)}
              {delta.consumed_by_job_id
                ? ` · job ${delta.consumed_by_job_id.slice(0, 8)}`
                : ""}
            </small>
          </article>
        ))}
      </div>
    </PageScaffold>
  );
}
