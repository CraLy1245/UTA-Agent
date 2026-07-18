import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useUiStore } from "../stores/uiStore";
import { App } from "./App";

const now = "2026-07-18T11:30:00Z";
const conversation = {
  id: "mock-1",
  title: "产品开发规划",
  created_at: now,
  updated_at: now,
};
const modelSetting = {
  role: "main",
  base_url: "https://api.openai.com/v1",
  model: "gpt-5.6",
  timeout_seconds: 120,
  max_output_tokens: 8192,
  temperature: null,
  api_key_env: "OPENAI_API_KEY",
  enabled: true,
  has_api_key: false,
  updated_at: now,
};

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
  close() {}
  emit(payload: object) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent<string>);
  }
}

function mockApi() {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/conversations") && init?.method !== "POST")
        return Response.json([conversation]);
      if (url.endsWith("/conversations/mock-1/turns"))
        return Response.json(
          {
            id: "turn-1",
            conversation_id: "mock-1",
            user_message_id: "user-2",
            source_turn_id: null,
            status: "pending",
            error_message: null,
            input_tokens: null,
            output_tokens: null,
          },
          { status: 201 },
        );
      if (url.endsWith("/turns/turn-1/cancel"))
        return Response.json({
          id: "turn-1",
          conversation_id: "mock-1",
          user_message_id: "user-2",
          source_turn_id: null,
          status: "running",
          error_message: null,
          input_tokens: null,
          output_tokens: null,
        });
      if (url.endsWith("/conversations/mock-1"))
        return Response.json({
          ...conversation,
          tool_executions: [],
          feedback_events: [],
          messages: [
            {
              id: "assistant-1",
              turn_id: "old-turn",
              role: "assistant",
              content: "已持久化的回答",
              sequence: 1,
              created_at: now,
            },
          ],
        });
      if (url.includes("/survival/status"))
        return Response.json({
          units_per_token: 100,
          accounts: [
            {
              account_type: "read",
              balance_units: 100_000_000_000,
              initial_balance_units: 100_000_000_000,
              updated_at: now,
            },
            {
              account_type: "output",
              balance_units: 10_000_000_000,
              initial_balance_units: 10_000_000_000,
              updated_at: now,
            },
          ],
          latest_turn: {
            turn_id: "old-turn",
            input_tokens: 1000,
            output_tokens: 300,
            read_change_units: -100_000,
            output_change_units: -30_000,
            completed_at: now,
          },
        });
      if (url.includes("/survival/transactions")) return Response.json([]);
      if (url.endsWith("/memory/status"))
        return Response.json({
          active_delta_char_count: 15,
          delta_char_limit: 2000,
          deferred_delta_char_count: 0,
          pending_count: 1,
          deferred_count: 0,
          formal_memory_char_count: 0,
          formal_memory_char_limit: 18000,
          current_memory_version: null,
        });
      if (url.endsWith("/memory") || url.includes("/memory?"))
        return Response.json([
          {
            id: "memory-1",
            revision_id: "revision-1",
            source_turn_id: "source-turn-1",
            raw_content: "以后不要使用 CLI",
            delta_type: "explicit_instruction",
            priority: 98,
            status: "pending",
            char_count: 15,
            consumed_by_job_id: null,
            created_at: now,
          },
        ]);
      if (url.endsWith("/turns/old-turn/feedback"))
        return Response.json({
          quality_feedback: {
            id: "feedback-1",
            turn_id: "old-turn",
            rating: "satisfied",
            comment: null,
            created_at: now,
          },
          survival_reward: {
            granted_now: true,
            transactions: [],
          },
        });
      if (url.endsWith("/model-settings/main"))
        return Response.json(modelSetting);
      if (url.endsWith("/tools/status"))
        return Response.json({
          enabled: true,
          workspace_path: "C:/workspace",
          available_tools: ["list_directory", "read_file", "write_file"],
        });
      throw new Error(`Unexpected request: ${url}`);
    });
}

function renderApp(path = "/chat/mock-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("phase 5 application", () => {
  beforeEach(() => {
    useUiStore.setState({
      conversationsCollapsed: false,
      statusCollapsed: false,
    });
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    mockApi();
  });
  afterEach(() => vi.restoreAllMocks());

  it("renders persistent conversation data and the three-column shell", async () => {
    renderApp();
    expect(
      await screen.findByRole("heading", { name: "产品开发规划" }),
    ).toBeInTheDocument();
    expect(screen.getByText("已持久化的回答")).toBeInTheDocument();
    expect(screen.getByText("Agent 状态")).toBeInTheDocument();
    expect(await screen.findByText("1,000,000,000.00")).toBeInTheDocument();
    expect(screen.getByText("100,000,000.00")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "折叠会话栏" }));
    expect(
      screen.getByRole("button", { name: "展开会话栏" }),
    ).toBeInTheDocument();
  });

  it("records satisfaction and explains the survival reward", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByText("已持久化的回答");

    await user.click(screen.getByRole("button", { name: "满意" }));

    expect(
      await screen.findByText("满意已记录，已精确返还本轮消耗的 108%。"),
    ).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/turns/old-turn/feedback"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ rating: "satisfied", comment: null }),
      }),
    );
  });

  it("starts a WebSocket stream, renders deltas, and sends cancellation", async () => {
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("heading", { name: "产品开发规划" });
    await user.type(
      screen.getByRole("textbox", { name: "消息内容" }),
      "新的问题",
    );
    await user.click(screen.getByRole("button", { name: "发送消息" }));
    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1));
    act(() =>
      FakeWebSocket.instances[0].emit({
        event: "tool.started",
        conversation_id: "mock-1",
        turn_id: "turn-1",
        timestamp: now,
        data: {
          tool: {
            id: "tool-1",
            turn_id: "turn-1",
            provider_call_id: "call-1",
            call_sequence: 1,
            tool_name: "read_file",
            arguments: { path: "notes.txt" },
            status: "running",
            result: null,
            error_message: null,
            started_at: now,
            completed_at: null,
          },
        },
      }),
    );
    expect(await screen.findByText("读取文件")).toBeInTheDocument();
    expect(screen.getByText("执行中")).toBeInTheDocument();
    act(() =>
      FakeWebSocket.instances[0].emit({
        event: "tool.completed",
        conversation_id: "mock-1",
        turn_id: "turn-1",
        timestamp: now,
        data: {
          tool: {
            id: "tool-1",
            turn_id: "turn-1",
            provider_call_id: "call-1",
            call_sequence: 1,
            tool_name: "read_file",
            arguments: { path: "notes.txt" },
            status: "completed",
            result: { ok: true, content: "hello" },
            error_message: null,
            started_at: now,
            completed_at: now,
          },
        },
      }),
    );
    expect(await screen.findByText("已完成")).toBeInTheDocument();
    act(() =>
      FakeWebSocket.instances[0].emit({
        event: "assistant.delta",
        conversation_id: "mock-1",
        turn_id: "turn-1",
        timestamp: now,
        data: { content: "流式片段" },
      }),
    );
    expect(await screen.findByText("流式片段")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "停止生成" }));
    await waitFor(() =>
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/turns/turn-1/cancel"),
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("opens the independent management pages", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(await screen.findByRole("link", { name: "记忆" }));
    expect(screen.getByRole("heading", { name: "记忆" })).toBeInTheDocument();
    expect(await screen.findByText("以后不要使用 CLI")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "记忆占用" })).getByText(
        "15 / 2000",
      ),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "技能" }));
    expect(screen.getByRole("heading", { name: "技能" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "活动" }));
    expect(
      screen.getByRole("heading", { name: "后台活动" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "设置" }));
    expect(screen.getByRole("heading", { name: "设置" })).toBeInTheDocument();
  });
});
