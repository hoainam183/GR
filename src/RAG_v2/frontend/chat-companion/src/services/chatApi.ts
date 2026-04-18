import axios from 'axios';
import type { ChatRequest, ChatResponse, UserContext } from '@/types/chat';

type StoredUserShape = UserContext & {
  email?: string | null;
  username?: string | null;
};

export interface ResolvedChatIdentity {
  userContext?: UserContext;
  userId?: string;
  source: 'explicit' | 'localStorage' | 'mixed' | 'none';
}

// Backend API endpoint
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Configure axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000 * 2, // 60*2 seconds timeout for RAG processing
  headers: {
    'Content-Type': 'application/json',
  },
});

const cleanText = (value: unknown): string | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const cleaned = value.trim();
  return cleaned.length > 0 ? cleaned : undefined;
};

const sanitizeUserContext = (
  context?: UserContext,
): UserContext | undefined => {
  if (!context) {
    return undefined;
  }

  const cleaned: UserContext = {};
  const studentId = cleanText(context.student_id);
  const cohort = cleanText(context.cohort);
  const major = cleanText(context.major);
  const majorCode = cleanText(context.major_code);
  const fullName = cleanText(context.full_name);

  if (studentId) cleaned.student_id = studentId;
  if (cohort) cleaned.cohort = cohort;
  if (major) cleaned.major = major;
  if (majorCode) cleaned.major_code = majorCode;
  if (fullName) cleaned.full_name = fullName;

  return Object.keys(cleaned).length > 0 ? cleaned : undefined;
};

const readStoredUser = (): StoredUserShape | undefined => {
  try {
    const raw = localStorage.getItem('user');
    if (!raw) {
      return undefined;
    }
    const parsed = JSON.parse(raw) as StoredUserShape;
    if (!parsed || typeof parsed !== 'object') {
      return undefined;
    }
    return parsed;
  } catch {
    return undefined;
  }
};

const storedUserToContext = (
  stored?: StoredUserShape,
): UserContext | undefined => {
  if (!stored) {
    return undefined;
  }
  return sanitizeUserContext({
    student_id: stored.student_id,
    cohort: stored.cohort,
    major: stored.major,
    major_code: stored.major_code,
    full_name: stored.full_name,
  });
};

export const resolveChatIdentity = (
  userContext?: UserContext,
  userId?: string,
): ResolvedChatIdentity => {
  const explicitContext = sanitizeUserContext(userContext);
  const explicitUserId = cleanText(userId);

  const storedUser = readStoredUser();
  const fallbackContext = storedUserToContext(storedUser);
  const fallbackUserId =
    cleanText(storedUser?.email) ||
    cleanText(storedUser?.username) ||
    cleanText(storedUser?.student_id);

  const resolvedContext = explicitContext || fallbackContext;
  const resolvedUserId = explicitUserId || fallbackUserId;

  const hasExplicit = Boolean(explicitContext || explicitUserId);
  const hasFallback = Boolean(fallbackContext || fallbackUserId);

  let source: ResolvedChatIdentity['source'] = 'none';
  if (hasExplicit && hasFallback && (!explicitContext || !explicitUserId)) {
    source = 'mixed';
  } else if (hasExplicit) {
    source = 'explicit';
  } else if (hasFallback) {
    source = 'localStorage';
  }

  return {
    userContext: resolvedContext,
    userId: resolvedUserId,
    source,
  };
};

export const sendMessage = async (
  question: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }> = [],
  topK: number = 5,
  sessionId?: string,
  userContext?: UserContext,
  userId?: string,
): Promise<ChatResponse> => {
  try {
    const identity = resolveChatIdentity(userContext, userId);

    const response = await apiClient.post<ChatResponse>('/chat', {
      question,
      top_k: topK,
      history,
      session_id: sessionId,
      user_context: identity.userContext,
      user_id: identity.userId,
    } as ChatRequest);
    
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('API Error:', error.response?.data || error.message);
      throw new Error(
        error.response?.data?.detail || 
        'Failed to get response from the server. Please make sure the backend is running.'
      );
    }
    throw error;
  }
};

// Health check endpoint
export const checkHealth = async (): Promise<boolean> => {
  try {
    const response = await apiClient.get('/health');
    return response.data.status === 'healthy';
  } catch (error) {
    console.error('Health check failed:', error);
    return false;
  }
};
