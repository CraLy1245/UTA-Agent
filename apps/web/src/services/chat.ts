import type {
  ConversationDetail,
  ConversationSummary,
  FeedbackResult,
  MemoryDelta,
  MemoryItem,
  MemoryRevision,
  CognitiveJob,
  MemoryStatus,
  ModelSetting,
  SurvivalStatus,
  Skill,
  SkillEvolution,
  SkillEvolutionEvent,
  TokenTransaction,
  ToolStatus,
  Turn,
} from "../types/chat";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(
      body?.detail ?? `Request failed with status ${response.status}`,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const chatApi = {
  listConversations: () => request<ConversationSummary[]>("/conversations"),
  getConversation: (id: string) =>
    request<ConversationDetail>(`/conversations/${id}`),
  createConversation: (title = "新对话") =>
    request<ConversationSummary>("/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  renameConversation: (id: string, title: string) =>
    request<ConversationSummary>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: "DELETE" }),
  createTurn: (conversationId: string, content: string) =>
    request<Turn>(`/conversations/${conversationId}/turns`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  cancelTurn: (turnId: string) =>
    request<Turn>(`/turns/${turnId}/cancel`, { method: "POST" }),
  regenerateTurn: (turnId: string) =>
    request<Turn>(`/turns/${turnId}/regenerate`, { method: "POST" }),
  getModelSetting: () => request<ModelSetting>("/model-settings/main"),
  getToolStatus: () => request<ToolStatus>("/tools/status"),
  getSurvivalStatus: (conversationId?: string) =>
    request<SurvivalStatus>(
      `/survival/status${conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ""}`,
    ),
  getTokenTransactions: (limit = 20) =>
    request<TokenTransaction[]>(`/survival/transactions?limit=${limit}`),
  getMemoryStatus: () => request<MemoryStatus>("/memory/status"),
  getMemoryDelta: (status?: string, query?: string) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (query) params.set("query", query);
    const suffix = params.size ? `?${params.toString()}` : "";
    return request<MemoryDelta[]>(`/memory${suffix}`);
  },
  getMemoryItems: (status?: string, query?: string) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (query) params.set("query", query);
    return request<MemoryItem[]>(`/memory/items${params.size ? `?${params}` : ""}`);
  },
  createMemoryItem: (payload: Pick<MemoryItem, "title" | "content" | "category" | "tags" | "priority">) =>
    request<MemoryItem>("/memory/items", { method: "POST", body: JSON.stringify(payload) }),
  updateMemoryItem: (item: MemoryItem, content: string) =>
    request<MemoryItem>(`/memory/items/${item.id}`, { method: "PATCH", body: JSON.stringify({ expected_revision_id: item.current_revision_id, content }) }),
  memoryAction: (itemId: string, action: "lock" | "unlock" | "archive" | "restore") =>
    request<MemoryItem>(`/memory/items/${itemId}/${action}`, { method: "POST" }),
  getMemoryRevisions: (itemId: string) => request<MemoryRevision[]>(`/memory/items/${itemId}/revisions`),
  rollbackMemory: (itemId: string, revisionId: string) => request<MemoryItem>(`/memory/items/${itemId}/rollback/${revisionId}`, { method: "POST" }),
  getCognitiveJobs: () => request<CognitiveJob[]>("/cognitive-jobs"),
  retryCognitiveJob: (jobId: string) => request<CognitiveJob>(`/cognitive-jobs/${jobId}/retry`, { method: "POST" }),
  getSkills: (status?: string, query?: string) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (query) params.set("query", query);
    return request<Skill[]>(`/skills${params.size ? `?${params}` : ""}`);
  },
  createSkill: (payload: Pick<Skill, "name" | "description" | "content"> & { reason: string }) =>
    request<Skill>("/skills", { method: "POST", body: JSON.stringify(payload) }),
  updateSkill: (skill: Skill, content: string) => request<Skill>(`/skills/${skill.id}`, {
    method: "PATCH",
    body: JSON.stringify({ expected_revision_id: skill.stable_revision_id, content, reason: "用户编辑" }),
  }),
  skillAction: (skillId: string, action: "lock" | "unlock" | "archive" | "restore") =>
    request<Skill>(`/skills/${skillId}/${action}`, { method: "POST" }),
  getSkillEvolution: (skillId: string) => request<SkillEvolution>(`/skills/${skillId}/evolution`),
  getSkillEvolutionEvents: () => request<SkillEvolutionEvent[]>("/skills/evolution-events"),
  candidateAction: (skillId: string, revisionId: string, action: "promote" | "reject" | "pause", reason: string) =>
    request<Skill>(`/skills/${skillId}/candidate/${revisionId}/${action}`, { method: "POST", body: JSON.stringify({ reason }) }),
  rollbackSkill: (skillId: string, revisionId: string) => request<Skill>(`/skills/${skillId}/rollback/${revisionId}`, { method: "POST", body: JSON.stringify({ reason: "用户手动回滚" }) }),
  submitFeedback: (
    turnId: string,
    rating: "satisfied" | "unsatisfied",
    comment?: string | null,
  ) =>
    request<FeedbackResult>(`/turns/${turnId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ rating, comment: comment || null }),
    }),
  updateModelSetting: (
    setting: Omit<
      ModelSetting,
      "role" | "api_key_env" | "has_api_key" | "updated_at"
    >,
  ) =>
    request<ModelSetting>("/model-settings/main", {
      method: "PUT",
      body: JSON.stringify(setting),
    }),
};

export function turnWebSocketUrl(turnId: string): string {
  const configured = import.meta.env.VITE_WS_BASE_URL as string | undefined;
  if (configured) return `${configured.replace(/\/$/, "")}/turns/${turnId}`;
  if (import.meta.env.DEV) return `ws://127.0.0.1:8000/api/ws/turns/${turnId}`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws/turns/${turnId}`;
}
