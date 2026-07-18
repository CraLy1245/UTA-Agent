import {
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Clock3,
  Database,
  Gauge,
  Sparkles,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { chatApi } from "../../services/chat";
import { useUiStore } from "../../stores/uiStore";

function Metric({
  label,
  value,
  detail,
  percent,
  tone = "green",
}: {
  label: string;
  value: string;
  detail: string;
  percent: number;
  tone?: "green" | "amber";
}) {
  return (
    <section className="status-card">
      <div className="status-card__heading">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <p>{detail}</p>
      <div className="progress-track">
        <span className={tone} style={{ width: `${percent}%` }} />
      </div>
    </section>
  );
}

const tokenFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatUnits(units: number): string {
  return tokenFormatter.format(units / 100);
}

function changeLabel(units: number | undefined): string {
  if (units === undefined) return "本会话还没有完成回合";
  const prefix = units > 0 ? "+" : "";
  return `本轮 ${prefix}${formatUnits(units)} Token`;
}

export function AgentSidebar() {
  const { conversationId = "new" } = useParams();
  const activeConversationId = conversationId === "new" ? undefined : conversationId;
  const collapsed = useUiStore((state) => state.statusCollapsed);
  const toggle = useUiStore((state) => state.toggleStatus);
  const setting = useQuery({
    queryKey: ["model-setting", "main"],
    queryFn: chatApi.getModelSetting,
  });
  const survival = useQuery({
    queryKey: ["survival-status", conversationId],
    queryFn: () => chatApi.getSurvivalStatus(activeConversationId),
  });
  const transactions = useQuery({
    queryKey: ["token-transactions"],
    queryFn: () => chatApi.getTokenTransactions(12),
  });
  const memory = useQuery({
    queryKey: ["memory-status"],
    queryFn: chatApi.getMemoryStatus,
  });
  const cognitiveJobs = useQuery({
    queryKey: ["cognitive-jobs"],
    queryFn: chatApi.getCognitiveJobs,
    refetchInterval: 3_000,
  });
  const latestCognitiveJob = cognitiveJobs.data?.[0];
  const cognitiveLabel = latestCognitiveJob
    ? latestCognitiveJob.status === "completed"
      ? `已整理 ${latestCognitiveJob.start_turn_number}—${latestCognitiveJob.end_turn_number}`
      : latestCognitiveJob.status === "failed"
        ? "失败待重试"
        : latestCognitiveJob.status === "conflict"
          ? "版本冲突"
          : "处理中"
    : "等待 20 回合";
  const readAccount = survival.data?.accounts.find(
    (account) => account.account_type === "read",
  );
  const outputAccount = survival.data?.accounts.find(
    (account) => account.account_type === "output",
  );
  const readPercent = readAccount
    ? Math.max(
        0,
        Math.min(
          100,
          (readAccount.balance_units / readAccount.initial_balance_units) * 100,
        ),
      )
    : 0;
  const outputPercent = outputAccount
    ? Math.max(
        0,
        Math.min(
          100,
          (outputAccount.balance_units / outputAccount.initial_balance_units) *
            100,
        ),
      )
    : 0;

  return (
    <aside className={`agent-sidebar ${collapsed ? "is-collapsed" : ""}`}>
      <header>
        <div>
          <span>Agent 状态</span>
          <small>第 7 阶段 Skill 演化</small>
        </div>
        <i aria-label="系统在线" />
      </header>
      <div className="agent-sidebar__content">
        <Metric
          label="主对话模型"
          value={setting.data?.model ?? "读取中…"}
          detail={
            setting.data?.has_api_key ? "环境密钥已就绪" : "缺少 OPENAI_API_KEY"
          }
          percent={setting.data?.has_api_key ? 100 : 8}
          tone={setting.data?.has_api_key ? "green" : "amber"}
        />
        <Metric
          label="读取 Token"
          value={
            readAccount
              ? `${formatUnits(readAccount.balance_units)}`
              : "读取中…"
          }
          detail={changeLabel(survival.data?.latest_turn?.read_change_units)}
          percent={readPercent}
          tone={readPercent < 10 ? "amber" : "green"}
        />
        <Metric
          label="输出 Token"
          value={
            outputAccount
              ? `${formatUnits(outputAccount.balance_units)}`
              : "读取中…"
          }
          detail={changeLabel(survival.data?.latest_turn?.output_change_units)}
          percent={outputPercent}
          tone={outputPercent < 10 ? "amber" : "green"}
        />
        <Metric
          label="实时记忆"
          value={
            memory.data
              ? `${memory.data.active_delta_char_count} / ${memory.data.delta_char_limit}`
              : "读取中…"
          }
          detail={
            memory.data?.deferred_count
              ? `${memory.data.deferred_count} 条等待认知整理`
              : `正式记忆 v${memory.data?.current_memory_version ?? 0}`
          }
          percent={
            memory.data
              ? (memory.data.active_delta_char_count /
                  memory.data.delta_char_limit) *
                100
              : 0
          }
          tone={
            (memory.data?.active_delta_char_count ?? 0) > 1_800
              ? "amber"
              : "green"
          }
        />

        <section className="status-card skill-card">
          <div className="status-card__heading">
            <span>当前 Skill</span>
            <Sparkles size={16} />
          </div>
          <strong>
            {survival.data?.latest_turn?.skill_revision_ids?.length ?? 0} 个
            Revision
          </strong>
          <p>
            {survival.data?.latest_turn?.skill_revision_ids?.length
              ? survival.data.latest_turn.skill_revision_ids
                  .map((id) => id.slice(0, 8))
                  .join(" · ")
              : "最近回合没有加载 Skill"}
          </p>
        </section>

        <section className="status-card jobs-card">
          <div className="status-card__heading">
            <span>后台任务</span>
            <Clock3 size={16} />
          </div>
          <p>
            <CircleCheck size={14} /> 会话持久化 <b>就绪</b>
          </p>
          <p>
            <Database size={14} /> WebSocket 流式 <b>就绪</b>
          </p>
          <p>
            <Gauge size={14} /> 认知整理 <b>{cognitiveLabel}</b>
          </p>
        </section>

        <details className="status-card transaction-history">
          <summary>
            <span>Token 交易历史</span>
            <strong>{transactions.data?.length ?? 0} 条</strong>
          </summary>
          <div>
            {(transactions.data ?? []).map((transaction) => (
              <article key={transaction.id}>
                <span>
                  {transaction.transaction_type === "survival_reward"
                    ? "满意奖励"
                    : "回合扣除"}
                  · {transaction.account_type === "read" ? "读取" : "输出"}
                </span>
                <b className={transaction.amount_units > 0 ? "positive" : ""}>
                  {transaction.amount_units > 0 ? "+" : ""}
                  {formatUnits(transaction.amount_units)}
                </b>
              </article>
            ))}
            {!transactions.isLoading && !transactions.data?.length ? (
              <p>还没有 Token 交易。</p>
            ) : null}
          </div>
        </details>
      </div>
      <button
        className="status-collapse"
        type="button"
        onClick={toggle}
        aria-label={collapsed ? "展开状态栏" : "折叠状态栏"}
      >
        {collapsed ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        <span>收起状态栏</span>
      </button>
    </aside>
  );
}
