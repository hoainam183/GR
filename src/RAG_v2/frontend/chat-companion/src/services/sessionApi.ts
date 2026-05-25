import axios from 'axios';
import type { Session, Turn } from '@/types/chat';
import { installAuthInterceptors } from '@/services/authSession';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

installAuthInterceptors(apiClient);

export const getSessions = async (_userId?: string): Promise<Session[]> => {
  // Always use the authenticated /sessions/me endpoint.
  // The axios client's request interceptor (ensureAccessToken) will attach the
  // Bearer token, refreshing via the HttpOnly cookie if the memory token has
  // been cleared by a page reload.  The legacy ?user_id= fallback was racy
  // (memory token not yet restored) and returned unscoped data.
  const response = await apiClient.get<{ sessions: Session[]; count: number }>('/sessions/me');
  return response.data.sessions;
};

export const getSession = async (
  sessionId: string,
): Promise<{ session: Session; turns: Turn[] }> => {
  const response = await apiClient.get<Session & { turns: Turn[] }>(`/session/${sessionId}`);
  const { turns, ...session } = response.data;
  return { session: session as Session, turns: turns ?? [] };
};

export const createSession = async (
  _userId?: string,
): Promise<{ session_id: string }> => {
  // Backend assigns user_id from JWT when authenticated; body.user_id is ignored.
  const response = await apiClient.post<{ session_id: string; created_at: string }>('/session', {});
  return { session_id: response.data.session_id };
};

export const deleteSession = async (sessionId: string): Promise<void> => {
  await apiClient.delete(`/session/${sessionId}`);
};

export const renameSession = async (
  sessionId: string,
  title: string,
): Promise<{ updated: boolean; session_id: string; title: string }> => {
  const response = await apiClient.patch<{
    updated: boolean;
    session_id: string;
    title: string;
  }>(`/session/${sessionId}`, { title });
  return response.data;
};
