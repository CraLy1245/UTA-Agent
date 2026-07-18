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

export function AgentSidebar() {
  const collapsed = useUiStore((state) => state.statusCollapsed);
  const toggle = useUiStore((state) => state.toggleStatus);
  const setting = useQuery({
    queryKey: ["model-setting", "main"],
    queryFn: chatApi.getModelSetting,
  });

  return (
    <aside className={`agent-sidebar ${collapsed ? "is-collapsed" : ""}`}>
      <header>
        <div>
          <span>Agent 状态</span>
          <small>第 2 阶段实时状态</small>
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
          label="输出 Token"
          value="第 4 阶段接入"
          detail="Provider usage 已可记录"
          percent={0}
        />
        <Metric
          label="长期记忆"
          value="第 5 阶段接入"
          detail="当前不显示虚构占用"
          percent={0}
        />

        <section className="status-card skill-card">
          <div className="status-card__heading">
            <span>当前 Skill</span>
            <Sparkles size={16} />
          </div>
          <strong>第 7 阶段接入</strong>
          <p>当前没有加载 Skill</p>
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
            <Gauge size={14} /> 认知整理 <b>待触发</b>
          </p>
        </section>
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
