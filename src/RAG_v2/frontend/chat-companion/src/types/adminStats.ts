// Admin statistics response types

// ─── EP1: Overview ────────────────────────────────────────
export interface OverviewStats {
  total_users: number;
  total_sessions: number;
  total_queries: number;
  active_users_7d: number;
  total_feedback: number;
  satisfaction_rate: number | null;
}

// ─── EP2: User list ───────────────────────────────────────
export interface AdminUser {
  _id: string;
  full_name: string;
  email: string | null;
  student_id: string;
  cohort: string;
  major: string;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string;
  session_count: number;
  query_count: number;
}

export interface AdminUsersResponse {
  users: AdminUser[];
  total: number;
  page: number;
  limit: number;
}

// ─── EP3: User breakdown ──────────────────────────────────
export interface UserBreakdown {
  by_role: Record<string, number>;
  registrations: Array<{ date: string; count: number }>;
}

// ─── EP4: Query analytics ─────────────────────────────────
export interface QueryAnalytics {
  volume: Array<{ date: string; count: number }>;
  latency: Array<{ date: string; avg_ms: number | null; p95_ms: number | null }>;
  by_route: Array<{ route: string; count: number }>;
  by_mode: Array<{ mode: string; count: number }>;
  top_questions: Array<{ question: string; count: number }>;
  error_count: number;
}

// ─── EP5: Agent analytics ─────────────────────────────────
export interface AgentAnalytics {
  total_calls: number;
  avg_iterations: number;
  error_rate: number;
  tavily_triggers: number;
  tool_frequency: Array<{ tool: string; count: number }>;
  daily_usage: Array<{ date: string; count: number }>;
}

// ─── EP6: Feedback topics ─────────────────────────────────
export interface FeedbackTopics {
  topics: Array<{
    question: string;
    category: string | null;
    count: number;
    last_at: string | null;
  }>;
}

// ─── EP7: System stats ────────────────────────────────────
export interface SystemStats {
  config: {
    agent_enabled: boolean;
    self_eval_enabled: boolean;
    tavily_fallback_enabled: boolean;
    crawler_enabled: boolean;
    redis_enabled: boolean;
    mongodb_enabled: boolean;
  };
  mongo_status: string;
  redis_status: string;
  documents_by_status: Record<string, number>;
  documents_by_collection: Record<string, number>;
  cache: Record<string, unknown> | null;
  crawler: {
    enabled: boolean;
    schedule_hour: number;
    schedule_minute: number;
  };
}

// ─── EP8: User status toggle ──────────────────────────────
export interface UserStatusResponse {
  ok: boolean;
  is_active: boolean;
}

// ─── EP9: Crawler trigger ─────────────────────────────────
export interface CrawlerTriggerResponse {
  ok: boolean;
  message: string;
  timeout_seconds: number;
}

// ─── EP10: Crawler status ─────────────────────────────────
export interface CrawlerStatus {
  is_running: boolean;
  last_result: {
    status: string;
    pipeline?: string;
    error?: string;
    completed_at?: string;
    [key: string]: unknown;
  } | null;
  cooldown_seconds: number;
}
