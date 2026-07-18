import { Activity, CheckCircle2, Clock3 } from "lucide-react";
import { PageScaffold } from "./PageScaffold";

export function ActivityPage() {
  return (
    <PageScaffold
      title="后台活动"
      description="认知任务与持久化工作的实时状态。"
      icon={Activity}
      action={<button className="secondary-button">手动刷新</button>}
    >
      <div className="activity-summary">
        <div>
          <b>0</b>
          <span>运行中</span>
        </div>
        <div>
          <b>1</b>
          <span>等待中</span>
        </div>
        <div>
          <b>12</b>
          <span>已完成</span>
        </div>
      </div>
      <div className="activity-table">
        <div className="table-head">
          <span>任务</span>
          <span>处理范围</span>
          <span>状态</span>
          <span>更新时间</span>
        </div>
        <div className="table-row">
          <span>
            <Clock3 />
            记忆整理
          </span>
          <span>回合 1—20</span>
          <span className="status-text pending">待触发</span>
          <span>—</span>
        </div>
        <div className="table-row">
          <span>
            <CheckCircle2 />
            记忆增量同步
          </span>
          <span>回合 13</span>
          <span className="status-text success">已完成</span>
          <span>19:19</span>
        </div>
      </div>
    </PageScaffold>
  );
}
