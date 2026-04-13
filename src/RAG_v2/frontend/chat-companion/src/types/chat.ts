export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: RetrievedDocument[];
  targetCollections?: string[];
  collectionScores?: CollectionScore[];
  reflectedQuestion?: string;
  timingsMs?: Record<string, number>;
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
  metadata: Record<string, any>;
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
  // Extended trace fields
  routing_probabilities?: Record<string, number>;
  reflection_prompt?: string;
  llm_prompt?: string;
  applied_filters?: FilterInfo[];
  collection_results?: CollectionResult[];
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
  intent?: string;
  reflected_question?: string | null;
  timestamp: string;
  num_sources?: number;
  timings_ms?: Record<string, number>;
  latency_ms?: number;
  sources?: RetrievedDocument[];
  collection_scores?: CollectionScore[];
  target_collections?: string[];
}
