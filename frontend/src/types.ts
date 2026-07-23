export type StepStatus = "pending" | "running" | "completed" | "skipped" | "error";

export interface WorkflowStep {
  id: string;
  nodes: string[];
  label: string;
  description: string;
  optional?: boolean;
  emoji?: string;
}

export interface StepState {
  id: string;
  status: StepStatus;
  startedAt?: string;
  completedAt?: string;
  detail?: string;
}

export interface AgentState {
  task_plan_summary?: string;
  agent_route?: string;
  db_guard_blocked?: boolean;
  db_guard_detail?: string;
  db_guard_layer?: string;
  messages?: Array<{
    content?: unknown;
    type?: string;
    tool_calls?: Array<{ name?: string; args?: unknown }>;
  }>;
  user_input?: string;
  web_search_enabled?: boolean;
  user_latitude?: number;
  user_longitude?: number;
  pdf_filename?: string;
  pdf_summarize_only?: boolean;
  generated_pdf_path?: string;
  generated_pdf_filename?: string;
}

export interface LogEntry {
  id: string;
  time: string;
  level: "info" | "success" | "warn" | "error";
  message: string;
}

export interface RunRequest {
  user_input: string;
  web_search_enabled: boolean;
  user_latitude: number;
  user_longitude: number;
  pdf_analysis_enabled?: boolean;
  pdf_data_base64?: string;
  pdf_filename?: string;
  pdf_summarize_only?: boolean;
  conversation_messages?: Array<{ type: "human" | "ai"; content: string }>;
}

export type AgentRunSettings = RunRequest;
