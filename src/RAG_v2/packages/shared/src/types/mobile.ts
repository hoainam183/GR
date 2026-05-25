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

export interface BookmarkUpdateRequest {
  folder?: string;
  note?: string;
}

export interface BookmarkFolderRenameRequest {
  new_name: string;
}

export interface FeedbackCreateRequest {
  session_id: string;
  turn_id: number;
  rating: 'up' | 'down';
  category?: 'wrong' | 'incomplete' | 'outdated';
  comment?: string;
}

export interface FeedbackResponse {
  id: string;
  session_id: string;
  turn_id: number;
  rating: 'up' | 'down' | null;
  category?: 'wrong' | 'incomplete' | 'outdated' | null;
  comment?: string | null;
  question: string;
  answer_snapshot: string;
  created_at: string;
  updated_at?: string;
}

export interface FeedbackStats {
  total: number;
  up: number;
  down: number;
  by_category: Record<string, number>;
  recent_days: number;
  with_comment?: number;
}

export interface LookupDocument {
  title: string;
  summary: string;
  source?: string | null;
  date?: string | null;
  url?: string | null;
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

export interface NotificationUnsubscribeRequest {
  expo_push_token: string;
  topics?: string[];
}

export interface NotificationUnreadCount {
  unread_count: number;
}
