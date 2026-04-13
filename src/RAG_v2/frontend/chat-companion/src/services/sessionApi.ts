import axios from 'axios';
import type { Session, Turn } from '@/types/chat';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

export const getSessions = async (userId: string): Promise<Session[]> => {
  const response = await apiClient.get<{ sessions: Session[]; count: number }>(
    '/sessions',
    { params: { user_id: userId } },
  );
  return response.data.sessions;
};

export const getSession = async (
  sessionId: string,
): Promise<{ session: Session; turns: Turn[] }> => {
  const response = await apiClient.get<Session & { turns: Turn[] }>(
    `/session/${sessionId}`,
  );
  const { turns, ...session } = response.data;
  return { session: session as Session, turns: turns ?? [] };
};

export const createSession = async (
  userId: string,
): Promise<{ session_id: string }> => {
  const response = await apiClient.post<{ session_id: string; created_at: string }>(
    '/session',
    { user_id: userId },
  );
  return { session_id: response.data.session_id };
};
