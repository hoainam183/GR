export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: RetrievedDocument[];
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

export interface ChatResponse {
  question: string;
  answer: string;
  retrieved_documents: RetrievedDocument[];
  num_documents: number;
  model_name: string;
  intent: string;
  session_id: string;
}
