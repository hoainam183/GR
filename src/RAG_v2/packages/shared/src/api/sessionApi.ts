/**
 * Session API functions — platform-agnostic.
 */

import type { AxiosInstance } from 'axios';
import type { Session, Turn } from '../types/chat';
import { API_PATHS } from '../utils/constants';

/**
 * List sessions for a user — GET /sessions?user_id=...
 */
export const getSessions = async (
  client: AxiosInstance,
  userId: string,
): Promise<Session[]> => {
  const response = await client.get<{ sessions: Session[]; count: number }>(
    API_PATHS.SESSIONS,
    { params: { user_id: userId } },
  );
  return response.data.sessions;
};

/**
 * Get a single session with its turns — GET /session/:id
 */
export const getSession = async (
  client: AxiosInstance,
  sessionId: string,
): Promise<{ session: Session; turns: Turn[] }> => {
  const response = await client.get<Session & { turns: Turn[] }>(
    `${API_PATHS.SESSION}/${sessionId}`,
  );
  const { turns, ...session } = response.data;
  return { session: session as Session, turns: turns ?? [] };
};

/**
 * Create a new empty session — POST /session
 */
export const createSession = async (
  client: AxiosInstance,
  userId: string,
): Promise<{ session_id: string }> => {
  const response = await client.post<{
    session_id: string;
    created_at: string;
  }>(API_PATHS.SESSION, { user_id: userId });
  return { session_id: response.data.session_id };
};
