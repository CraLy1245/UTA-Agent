import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  GitCompareArrows,
  History,
  Lock,
  Pause,
  RotateCcw,
  Search,
  Sparkles,
  Unlock,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { chatApi } from "../../services/chat";
import type { Skill, SkillUsage } from "../../types/chat";
import { PageScaffold } from "./PageScaffold";

const template = `name:reusable-workflow
description:描述这个工作流解决的问题
applicable_scenarios:
- 适用场景
safety_constraints:
- 保留安全和权限边界
steps:
- 读取真实上下文
- 执行并验证结果
success_criteria:
- 结果可追溯且通过验证`;

function rate(usages: SkillUsage[]) {
  const rated = usages.filter((usage) => usage.feedback);
  if (!rated.length) return "—";
  return `${Math.round((rated.filter((usage) => usage.feedback === "satisfied").length / rated.length) * 100)}%`;
}

export function SkillsPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("active");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const skills = useQuery({
    queryKey: ["skills", status, query],
    queryFn: () => chatApi.getSkills(status, query),
  });
  const evolution = useQuery({
    queryKey: ["skill-evolution", selectedId],
    queryFn: () => chatApi.getSkillEvolution(selectedId!),
    enabled: Boolean(selectedId),
  });
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["skills"] });
    await queryClient.invalidateQueries({ queryKey: ["skill-evolution"] });
    await queryClient.invalidateQueries({ queryKey: ["skill-evolution-events"] });
  };
  const create = useMutation({
    mutationFn: () => chatApi.createSkill({ name, description, content: draft, reason: "用户通过图形界面创建" }),
    onSuccess: async (skill) => {
      setCreating(false);
      setSelectedId(skill.id);
      setName(""); setDescription(""); setDraft("");
      await refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({ skill, content }: { skill: Skill; content: string }) => chatApi.updateSkill(skill, content),
    onSuccess: async () => { setEditing(false); await refresh(); },
  });
  const action = useMutation({
    mutationFn: ({ skillId, value }: { skillId: string; value: "lock" | "unlock" | "archive" | "restore" }) => chatApi.skillAction(skillId, value),
    onSuccess: refresh,
  });
  const candidateAction = useMutation({
    mutationFn: ({ skillId, revisionId, value }: { skillId: string; revisionId: string; value: "promote" | "reject" | "pause" }) =>
      chatApi.candidateAction(skillId, revisionId, value, `用户手动${value}`),
    onSuccess: refresh,
  });
  const rollback = useMutation({
    mutationFn: ({ skillId, revisionId }: { skillId: string; revisionId: string }) => chatApi.rollbackSkill(skillId, revisionId),
    onSuccess: refresh,
  });

  const activeCount = (skills.data ?? []).filter((skill) => skill.status === "active").length;
  const selected = evolution.data?.skill;
  const metrics = useMemo(() => {
    if (!evolution.data || !selected) return null;
    const stable = evolution.data.usages.filter((usage) => usage.skill_revision_id === selected.stable_revision_id);
    const candidate = evolution.data.usages.filter((usage) => usage.skill_revision_id === selected.candidate_revision_id);
    const average = (items: SkillUsage[]) => items.length ? Math.round(items.reduce((sum, item) => sum + item.input_tokens + item.output_tokens, 0) / items.length) : 0;
    return { stable, candidate, stableAverage: average(stable), candidateAverage: average(candidate) };
  }, [evolution.data, selected]);

  const error = create.error ?? update.error ?? action.error ?? candidateAction.error ?? rollback.error;
  return (
    <PageScaffold
      title="技能"
      description="稳定版本持续服务，候选版本按确定性 9:1 小规模试用；全部变化可审计和回滚。"
      icon={Sparkles}
      action={<button className="primary-button" onClick={() => { setCreating(true); setDraft(template); }}><Sparkles />新建 Skill</button>}
    >
      <div className="page-toolbar">
        <label><Search /><input aria-label="搜索 Skill" placeholder="搜索 Skill" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <select aria-label="Skill 状态" value={status} onChange={(event) => setStatus(event.target.value)}><option value="active">活跃 Skill</option><option value="archived">已归档</option></select>
        <span>{activeCount} / 50 个活跃</span>
      </div>
      {error ? <p className="empty-state error">{error.message}</p> : null}
      {creating ? <section className="skill-editor"><header><strong>创建可复用 Skill</strong><button aria-label="关闭创建" onClick={() => setCreating(false)}><X /></button></header><div className="form-grid"><label>名称<input value={name} onChange={(event) => setName(event.target.value)} /></label><label>说明<input value={description} onChange={(event) => setDescription(event.target.value)} /></label></div><textarea aria-label="Skill 内容" value={draft} onChange={(event) => setDraft(event.target.value)} /><button className="primary-button" disabled={!name || !description || !draft || create.isPending} onClick={() => create.mutate()}>保存 Skill</button></section> : null}
      <div className="skill-grid">
        {(skills.data ?? []).map((skill) => <article key={skill.id} className={selectedId === skill.id ? "selected" : ""}><Sparkles /><div><header><h2>{skill.name}</h2>{skill.candidate_revision_id ? <span className="candidate-badge">Candidate</span> : <span>{skill.status}</span>}</header><p>{skill.description}</p><dl><div><dt>有效使用</dt><dd>{skill.use_count}</dd></div><div><dt>满意率</dt><dd>{skill.satisfaction_rate === null ? "—" : `${Math.round(skill.satisfaction_rate * 100)}%`}</dd></div><div><dt>置信度</dt><dd>{Math.round(skill.confidence_score * 100)}%</dd></div></dl><div className="skill-actions"><button onClick={() => setSelectedId(skill.id)}><History />演化记录</button><button onClick={() => action.mutate({ skillId: skill.id, value: skill.locked ? "unlock" : "lock" })}>{skill.locked ? <Unlock /> : <Lock />}{skill.locked ? "解锁" : "锁定"}</button><button onClick={() => action.mutate({ skillId: skill.id, value: skill.status === "active" ? "archive" : "restore" })}>{skill.status === "active" ? <Archive /> : <RotateCcw />}{skill.status === "active" ? "归档" : "恢复"}</button></div></div></article>)}
      </div>
      {!skills.isLoading && !skills.data?.length ? <p className="empty-state">没有符合条件的 Skill。重复任务达到阈值或用户明确保存后，Worker 才会创建通用 Skill。</p> : null}
      {selected && metrics ? <section className="skill-evolution"><header><div><GitCompareArrows /><div><strong>{selected.name} · 版本演化</strong><small>Stable {selected.stable_revision_id.slice(0, 8)} · {selected.locked ? "用户已锁定" : "允许确定性路由"}</small></div></div><button aria-label="关闭演化记录" onClick={() => setSelectedId(null)}><X /></button></header><div className="competition-grid"><article><span>稳定版本</span><b>{metrics.stable.length} 次</b><small>满意率 {rate(metrics.stable)} · 均值 {metrics.stableAverage} Token</small></article><article><span>候选版本</span><b>{metrics.candidate.length} / 5 次</b><small>满意率 {rate(metrics.candidate)} · 均值 {metrics.candidateAverage} Token</small></article><article><span>路由策略</span><b>9 : 1</b><small>固定序列，可完整重放</small></article></div>{selected.candidate_revision_id ? <div className="candidate-controls"><button onClick={() => candidateAction.mutate({ skillId: selected.id, revisionId: selected.candidate_revision_id!, value: "pause" })}><Pause />暂停试用</button><button onClick={() => candidateAction.mutate({ skillId: selected.id, revisionId: selected.candidate_revision_id!, value: "promote" })}>手动晋升</button><button onClick={() => candidateAction.mutate({ skillId: selected.id, revisionId: selected.candidate_revision_id!, value: "reject" })}>拒绝候选</button></div> : null}<div className="skill-content"><header><strong>当前稳定内容</strong><button onClick={() => { setDraft(selected.content); setEditing(true); }}>编辑</button></header>{editing ? <><textarea value={draft} onChange={(event) => setDraft(event.target.value)} /><button className="primary-button" onClick={() => update.mutate({ skill: selected, content: draft })}>创建新稳定 Revision</button></> : <pre>{selected.content}</pre>}</div><h3>版本历史</h3><div className="revision-list">{evolution.data?.revisions.map((revision) => <article key={revision.id}><div><b>{revision.status}</b><span>{revision.operation} · {revision.id.slice(0, 8)}</span><time>{new Date(revision.created_at).toLocaleString()}</time></div><p>{revision.reason ?? "无说明"}</p><small>来源回合 {revision.source_turn_ids.length} · {revision.created_by}</small>{revision.id !== selected.stable_revision_id && revision.status !== "candidate" ? <button onClick={() => rollback.mutate({ skillId: selected.id, revisionId: revision.id })}><RotateCcw />回滚到此版本</button> : null}</article>)}</div></section> : null}
    </PageScaffold>
  );
}
