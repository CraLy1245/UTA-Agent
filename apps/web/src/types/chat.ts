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
    tool?: ToolExecution;
  };
};
