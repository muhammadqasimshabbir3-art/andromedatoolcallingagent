export type StepStatus = "pending" | "running" | "completed" | "skipped" | "error";

export type WorkflowAction = "analyze" | "report" | "email";

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

export interface CommentRow {
  author?: string;
  text?: string;
  category?: string;
  engagement_priority?: string;
  sentiment_score?: number | string;
  likes?: number;
  timestamp?: string;
  replied?: boolean;
  reply_text?: string;
  posted?: boolean;
  post_error?: string;
}

export interface AgentState {
  task_plan_summary?: string;
  agent_route?: string;
  messages?: Array<{ content?: string; type?: string; tool_calls?: any[] }>;
  user_input?: string;
  web_search_enabled?: boolean;
}

export interface VideoMetadata {
  title?: string;
  url?: string;
  video_id?: string;
  thumbnail_url?: string;
  views?: string;
  likes?: string;
  published?: string;
  comment_count?: string;
  video_about?: string;
  description?: string;
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
}

export type AgentRunSettings = Omit<RunRequest, never>;
