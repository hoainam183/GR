import type { AxiosInstance } from 'axios';
import type { FeedbackCreateRequest, FeedbackResponse, FeedbackStats } from '../types/mobile';
import { API_PATHS } from '../utils/constants';

export const submitFeedback = async (
  client: AxiosInstance,
  data: FeedbackCreateRequest,
): Promise<{ feedback_id: string; feedback: FeedbackResponse }> => {
  const response = await client.post<{ feedback_id: string; feedback: FeedbackResponse }>(
    API_PATHS.FEEDBACK,
    data,
  );
  return response.data;
};

export const deleteFeedback = async (
  client: AxiosInstance,
  sessionId: string,
  turnId: number,
): Promise<void> => {
  await client.delete(API_PATHS.FEEDBACK, { params: { session_id: sessionId, turn_id: turnId } });
};

export const getFeedback = async (
  client: AxiosInstance,
  sessionId: string,
  turnId: number,
): Promise<FeedbackResponse | null> => {
  const response = await client.get<{ feedback: FeedbackResponse | null }>(
    API_PATHS.FEEDBACK,
    { params: { session_id: sessionId, turn_id: turnId } },
  );
  return response.data.feedback;
};

export const getFeedbackStats = async (
  client: AxiosInstance,
  days = 30,
): Promise<FeedbackStats> => {
  const response = await client.get<{ stats: FeedbackStats }>(
    `${API_PATHS.FEEDBACK}/stats`,
    { params: { days } },
  );
  return response.data.stats;
};

export const listAllFeedback = async (
  client: AxiosInstance,
  params?: {
    rating?: 'up' | 'down' | 'all';
    category?: string;
    days?: number;
    page?: number;
    limit?: number;
  },
): Promise<{ feedbacks: FeedbackResponse[]; total: number; page: number; limit: number }> => {
  const response = await client.get<{
    feedbacks: FeedbackResponse[];
    total: number;
    page: number;
    limit: number;
  }>(`${API_PATHS.FEEDBACK}/list`, { params });
  return response.data;
};
