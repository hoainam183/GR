import type { AxiosInstance } from 'axios';
import type { FeedbackCreateRequest } from '../types/mobile';
import { API_PATHS } from '../utils/constants';

export const submitFeedback = async (
  client: AxiosInstance,
  data: FeedbackCreateRequest,
): Promise<{ feedback_id: string }> => {
  const response = await client.post<{ feedback_id: string }>(
    API_PATHS.FEEDBACK,
    data,
  );
  return response.data;
};
