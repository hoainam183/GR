import type { RetrievedDocument } from './chat';

export interface Bookmark {
  id: string;
  session_id: string;
  turn_id: number;
  question: string;
  answer_preview: string;
  answer_snapshot: string;
  sources_snapshot: RetrievedDocument[];
  folder: string;
  note?: string | null;
  created_at: string;
  updated_at?: string;
}

export interface BookmarkFolder {
  name: string;
  count: number;
}

export interface BookmarkCreateRequest {
  session_id: string;
  turn_id: number;
  folder?: string;
  note?: string;
}

export interface FeedbackCreateRequest {
  session_id: string;
  turn_id: number;
  rating: 'up' | 'down';
  category?: 'wrong' | 'incomplete' | 'outdated';
  comment?: string;
}

export interface LookupDocument {
  title: string;
  summary: string;
  collection?: string | null;
  score: number;
  metadata: Record<string, unknown>;
}

export interface SuggestedQuestion {
  question: string;
  category: string;
  popularity: number;
}

export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  type: string;
  related_doc_id?: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationSubscribeRequest {
  topics: string[];
  expo_push_token: string;
}
