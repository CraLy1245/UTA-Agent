import {
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  Clock3,
  Database,
  Gauge,
  Sparkles,
} from "lucide-react";

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

  return (
    <aside className={`agent-sidebar ${collapsed ? "is-collapsed" : ""}`}>
      <header>
        <div>
          <span>Agent 状态</span>
          <small>Mock 数据</small>
        </div>
        <i aria-label="系统在线" />
      </header>
      <div className="agent-sidebar__content">
        <Metric
          label="读取 Token"
          value="999,981,568"
          detail="本轮已用 18,432"
          percent={72}
        />
        <Metric
          label="输出 Token"
          value="99,997,814"
          detail="本轮已用 2,186"
          percent={54}
        />
        <Metric
          label="长期记忆"
          value="7,360 / 18,000"
          detail="实时增量 286 / 2,000 字符"
          percent={41}
        />
        <Metric
          label="下次整理"
          value="还差 7 回合"
          detail="已完成 13 / 20 回合"
          percent={65}
          tone="amber"
        />

        <section className="status-card skill-card">
          <div className="status-card__heading">
            <span>当前 Skill</span>
            <Sparkles size={16} />
          </div>
          <strong>项目开发协作</strong>
          <p>已加载 1 / 3</p>
        </section>

        <section className="status-card jobs-card">
          <div className="status-card__heading">
            <span>后台任务</span>
            <Clock3 size={16} />
          </div>
          <p>
            <CircleCheck size={14} /> 记忆增量同步 <b>完成</b>
          </p>
          <p>
            <Database size={14} /> 数据快照 <b>空闲</b>
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
