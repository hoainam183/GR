import type { AxiosInstance } from 'axios';
import type {
  NotificationItem,
  NotificationSubscribeRequest,
} from '../types/mobile';
import { API_PATHS } from '../utils/constants';

export const listNotifications = async (
  client: AxiosInstance,
  unreadOnly = false,
): Promise<NotificationItem[]> => {
  const response = await client.get<{ notifications: NotificationItem[] }>(
    API_PATHS.NOTIFICATIONS,
    { params: unreadOnly ? { unread_only: true } : undefined },
  );
  return response.data.notifications;
};

export const markNotificationRead = async (
  client: AxiosInstance,
  notificationId: string,
): Promise<void> => {
  await client.put(`${API_PATHS.NOTIFICATIONS}/${notificationId}/read`);
};

export const subscribeNotifications = async (
  client: AxiosInstance,
  data: NotificationSubscribeRequest,
): Promise<{ subscribed_topics: string[] }> => {
  const response = await client.post<{ subscribed_topics: string[] }>(
    API_PATHS.NOTIFICATION_SUBSCRIBE,
    data,
  );
  return response.data;
};
