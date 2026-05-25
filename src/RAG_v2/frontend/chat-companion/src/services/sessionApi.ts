import axios from 'axios';
import type { Session, Turn } from '@/types/chat';
import { getStoredToken } from '@/services/authStorage';
import { installAuthInterceptors } from '@/services/authSession';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

installAuthInterceptors(apiClient);

const authHeaders = (): Record<string, string> => {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const getSessions = async (userId: string): Promise<Session[]> => {
  const token = getStoredToken();
  if (token) {
    const response = await apiClient.get<{ sessions: Session[]; count: number }>(
      '/sessions/me',
      { headers: authHeaders() },
    );
    return response.data.sessions;
  }

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
    { headers: authHeaders() },
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
    { headers: authHeaders() },
  );
  return { session_id: response.data.session_id };
};

export const deleteSession = async (sessionId: string): Promise<void> => {
  await apiClient.delete(`/session/${sessionId}`, {
    headers: authHeaders(),
  });
};

export const renameSession = async (
  sessionId: string,
  title: string,
): Promise<{ updated: boolean; session_id: string; title: string }> => {
  const response = await apiClient.patch<{
    updated: boolean;
    session_id: string;
    title: string;
  }>(
    `/session/${sessionId}`,
    { title },
    { headers: authHeaders() },
  );
  return response.data;
};
