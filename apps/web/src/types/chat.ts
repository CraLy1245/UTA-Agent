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
  completed_number?: number | null;
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

export type MemoryDelta = {
  id: string;
  revision_id: string;
  source_turn_id: string;
  raw_content: string;
  delta_type: "explicit_instruction";
  priority: number;
  status: "pending" | "deferred_capacity" | "duplicate_merged" | "consumed";
  char_count: number;
  consumed_by_job_id: string | null;
  created_at: string;
};

export type MemoryStatus = {
  active_delta_char_count: number;
  delta_char_limit: number;
  deferred_delta_char_count: number;
  pending_count: number;
  deferred_count: number;
  formal_memory_char_count: number;
  formal_memory_char_limit: number;
  current_memory_version: number | null;
};

export type MemoryItem = {
  id: string;
  category: string;
  title: string;
  content: string;
  tags: string[];
  priority: number;
  status: "active" | "archived" | "superseded";
  locked: boolean;
  current_revision_id: string;
  char_count: number;
  created_at: string;
  updated_at: string;
};

export type MemoryRevision = {
  id: string;
  memory_item_id: string;
  previous_revision_id: string | null;
  operation: string;
  title: string;
  content: string;
  category: string;
  priority: number;
  status: string;
  locked: boolean;
  source_turn_ids: string[];
  cognitive_job_id: string | null;
  created_by: string;
  reason: string | null;
  created_at: string;
};

export type CognitiveJob = {
  id: string;
  job_type: string;
  start_turn_number: number;
  end_turn_number: number;
  status: "pending" | "running" | "validating" | "committing" | "completed" | "failed" | "conflict";
  memory_version_before: number;
  memory_version_after: number | null;
  attempt_count: number;
  error_message: string | null;
  result_json: string | null;
  next_attempt_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
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
    memory_delta?: Pick<
      MemoryDelta,
      | "id"
      | "revision_id"
      | "source_turn_id"
      | "delta_type"
      | "priority"
      | "status"
      | "char_count"
    >;
  };
};
