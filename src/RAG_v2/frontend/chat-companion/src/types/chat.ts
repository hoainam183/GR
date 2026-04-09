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

export interface ChatRequest {
  question: string;
  top_k?: number;
  history?: Array<{ role: 'user' | 'assistant'; content: string }>;
  session_id?: string;
}

export interface RetrievedDocument {
  rank: number;
  content: string;
  score: number;
  metadata: Record<string, any>;
}

export interface CollectionScore {
  collection: string;
  score: number;
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
}
