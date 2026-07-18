export type Message = {
  id: string;
  turn_id: string | null;
  role: "user" | "assistant";
  content: string;
  sequence: number;
  created_at: string;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ToolExecution = {
  id: string;
  turn_id: string;
  provider_call_id: string;
  call_sequence: number;
  tool_name: "list_directory" | "read_file" | "write_file" | string;
  arguments: Record<string, unknown>;
  status: "running" | "completed" | "failed";
  result: Record<string, unknown> | null;
  error_message: string | null;
  created_at?: string;
  started_at: string | null;
  completed_at: string | null;
};

export type ConversationDetail = ConversationSummary & {
  messages: Message[];
  tool_executions: ToolExecution[];
  feedback_events: FeedbackEvent[];
};

export type FeedbackEvent = {
  id: string;
  turn_id: string;
  rating: "satisfied" | "unsatisfied";
  comment: string | null;
  created_at: string;
};

export type Turn = {
  id: string;
  conversation_id: string;
  user_message_id: string;
  source_turn_id: string | null;
  status: "pending" | "running" | "completed" | "cancelled" | "failed";
  error_message: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
};

export type ModelSetting = {
  role: string;
  base_url: string;
  model: string;
  timeout_seconds: number;
  max_output_tokens: number;
  temperature: number | null;
  api_key_env: string;
  enabled: boolean;
  has_api_key: boolean;
  updated_at: string;
};

export type ToolStatus = {
  enabled: boolean;
  workspace_path: string;
  available_tools: string[];
};

export type TokenAccount = {
  account_type: "read" | "output";
  balance_units: number;
  initial_balance_units: number;
  updated_at: string;
};

export type SurvivalStatus = {
  units_per_token: number;
  accounts: TokenAccount[];
  latest_turn: {
    turn_id: string;
    input_tokens: number;
    output_tokens: number;
    read_change_units: number;
    output_change_units: number;
    completed_at: string;
  } | null;
};

export type TokenTransaction = {
  id: string;
  turn_id: string | null;
  feedback_event_id: string | null;
  account_type: "read" | "output";
  transaction_type: "usage_debit" | "survival_reward" | string;
  amount_units: number;
  balance_before: number;
  balance_after: number;
  idempotency_key: string;
  metadata_value: Record<string, unknown>;
  created_at: string;
};

export type FeedbackResult = {
  quality_feedback: FeedbackEvent;
  survival_reward: {
    granted_now: boolean;
    transactions: TokenTransaction[];
  };
};

export type StreamEvent = {
  event: string;
  conversation_id: string;
  turn_id: string;
  timestamp: string;
  data: {
    content?: string;
    message?: Message | string;
    input_tokens?: number;
    output_tokens?: number;
    usage_complete?: boolean;
    accounts?: Record<
      string,
      { balance_units: number; initial_balance_units: number }
    >;
    turn_change_units?: Record<string, number>;
    tool?: ToolExecution;
  };
};
