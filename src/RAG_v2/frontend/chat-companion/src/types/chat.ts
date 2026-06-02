export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sessionId?: string;
  turnId?: number;
  modelName?: string;
  sources?: RetrievedDocument[];
  targetCollections?: string[];
  collectionScores?: CollectionScore[];
  routingProbabilities?: Record<string, number>;
  appliedFilters?: FilterInfo[];
  collectionResults?: CollectionResult[];
  reflectedQuestion?: string;
  timingsMs?: Record<string, number>;
  mode?: string;
  route?: string;
  toolsUsed?: string[];
  toolCalls?: AgentToolCall[];
  iterations?: number;
  error?: string;
  agentError?: string;
  agentTrace?: AgentTracePayload | null;
  isStreaming?: boolean;
}

export interface UserContext {
  student_id?: string;
  cohort?: string;
  major?: string;
  major_code?: string;
  full_name?: string;
}

export interface ChatRequest {
  question: string;
  mode?: 'auto' | 'rag' | 'agent';
  top_k?: number;
  history?: Array<{ role: 'user' | 'assistant'; content: string }>;
  session_id?: string;
  user_context?: UserContext;
  user_id?: string;
}

export interface RetrievedDocument {
  rank: number;
  content: string;
  score: number;           // final score (rerank if available, else hybrid)
  hybrid_score?: number;   // pre-rerank fusion score
  rerank_score?: number;   // cross-encoder score
  vector_score?: number;   // raw Qdrant cosine score
  keyword_score?: number;  // raw BM25 score
  collection?: string;     // source collection name
  metadata: Record<string, unknown>;
}

export interface CollectionScore {
  collection: string;
  score: number;
}

export interface FilterInfo {
  collection: string;
  applied: boolean;
  matched_ids: number;
  filter_desc?: string;
}

export interface CollectionResult {
  collection: string;
  vector_count: number;
  keyword_count: number;
}

export interface ChatResponse {
  question: string;
  answer: string;
  retrieved_documents: RetrievedDocument[];
  num_documents: number;
  model_name: string;
  intent: string;
  target_collections?: string[];
  collection_scores?: CollectionScore[];
  reflected_question?: string;
  timings_ms?: Record<string, number>;
  session_id: string;
  turn_id?: number;
  // Extended trace fields
  routing_probabilities?: Record<string, number>;
  reflection_prompt?: string;
  llm_prompt?: string;
  applied_filters?: FilterInfo[];
  collection_results?: CollectionResult[];
  context_trace?: Record<string, unknown>;
  rerank_trace?: Record<string, unknown>;
  answer_quality_gate?: Record<string, unknown>;
  fusion_weights?: Record<string, unknown>;
  answer_status?: string;
  mode?: string;
  route?: string;
  tools_used?: string[];
  tool_calls?: AgentToolCall[];
  iterations?: number;
  error?: string | null;
  agent_error?: string | null;
  agent_trace?: AgentTracePayload | null;
}

export interface AgentToolCall {
  tool: string;
  args: Record<string, unknown>;
  result: string;
  iteration: number;
  latency_ms?: number;
  timestamp?: string;
}

export interface AgentTracePayload {
  query?: string;
  session_id?: string;
  route?: string;
  execution_path?: string;
  complexity_subtype?: string;
  sub_questions?: string[];
  retrieval_plan?: Record<string, unknown>;
  decompose_trace?: Record<string, unknown>;
  planner_trace?: Record<string, unknown>;
  executor_results?: Array<Record<string, unknown>>;
  synthesis_trace?: Record<string, unknown>;
  iterations?: number;
  tool_calls?: AgentToolCall[];
  tool_names_sequence?: string[];
  final_answer_length?: number;
  latency_ms?: number;
  error?: string | null;
}

export interface ChatV3Response extends ChatResponse {
  mode?: string;
  route?: string;
  tools_used?: string[];
  tool_calls?: AgentToolCall[];
  iterations?: number;
  error?: string | null;
  agent_error?: string | null;
  agent_trace?: AgentTracePayload | null;
}

export interface Session {
  session_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  turn_count: number;
  user_id?: string | null;
}

export interface Turn {
  turn_id: number;
  session_id: string;
  question: string;
  answer: string;
  model_name?: string;
  intent?: string;
  reflected_question?: string | null;
  timestamp: string;
  num_sources?: number;
  timings_ms?: Record<string, number>;
  latency_ms?: number;
  sources?: RetrievedDocument[];
  collection_scores?: CollectionScore[];
  target_collections?: string[];
  routing_probabilities?: Record<string, number>;
  applied_filters?: FilterInfo[];
  collection_results?: CollectionResult[];
  context_trace?: Record<string, unknown>;
  rerank_trace?: Record<string, unknown>;
  answer_quality_gate?: Record<string, unknown>;
  fusion_weights?: Record<string, unknown>;
  answer_status?: string;
  mode?: string;
  route?: string;
  tools_used?: string[];
  tool_calls?: AgentToolCall[];
  iterations?: number;
  error?: string | null;
  agent_error?: string | null;
  agent_trace?: AgentTracePayload | null;
}
