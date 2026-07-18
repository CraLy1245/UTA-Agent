import type {
  ConversationDetail,
  ConversationSummary,
  FeedbackResult,
  ModelSetting,
  SurvivalStatus,
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
