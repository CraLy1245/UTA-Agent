import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, CheckCircle2, Clock3, RefreshCw } from "lucide-react";
import { chatApi } from "../../services/chat";
import { PageScaffold } from "./PageScaffold";

const labels: Record<string, string> = { pending: "等待中", running: "运行中", validating: "校验中", committing: "提交中", completed: "已完成", failed: "失败", conflict: "版本冲突" };
export function ActivityPage() {
  const client = useQueryClient();
  const jobs = useQuery({ queryKey: ["cognitive-jobs"], queryFn: chatApi.getCognitiveJobs, refetchInterval: 3000 });
  const retry = useMutation({ mutationFn: chatApi.retryCognitiveJob, onSuccess: () => client.invalidateQueries({ queryKey: ["cognitive-jobs"] }) });
  const data = jobs.data ?? [];
  const running = data.filter((job) => ["running", "validating", "committing"].includes(job.status)).length;
  return <PageScaffold title="后台活动" description="Cognitive Worker 与前台解耦；失败不会替换旧记忆。" icon={Activity} action={<button className="secondary-button" onClick={() => jobs.refetch()}><RefreshCw />手动刷新</button>}>
    <div className="activity-summary"><div><b>{running}</b><span>运行中</span></div><div><b>{data.filter((job) => job.status === "pending").length}</b><span>等待中</span></div><div><b>{data.filter((job) => job.status === "completed").length}</b><span>已完成</span></div></div>
    <div className="activity-table"><div className="table-head"><span>任务</span><span>处理范围</span><span>状态</span><span>结果 / 操作</span></div>{data.map((job) => { const result = job.result_json ? JSON.parse(job.result_json) as { summary?: string; counts?: Record<string, number> } : null; return <div className="table-row job-row" key={job.id}><span>{job.status === "completed" ? <CheckCircle2 /> : job.status === "failed" ? <AlertTriangle /> : <Clock3 />}认知记忆整理</span><span>回合 {job.start_turn_number}—{job.end_turn_number}</span><span className={`status-text ${job.status === "completed" ? "success" : job.status}`}>{labels[job.status]} · 尝试 {job.attempt_count}</span><span>{job.error_message ?? result?.summary ?? "—"}{["failed", "conflict"].includes(job.status) ? <button onClick={() => retry.mutate(job.id)}>重试</button> : null}</span></div>; })}{!jobs.isLoading && !data.length ? <p className="empty-state">尚未达到首个 20 个完整回合。</p> : null}{jobs.isError ? <p className="empty-state error">后台活动读取失败。</p> : null}</div>
  </PageScaffold>;
}
