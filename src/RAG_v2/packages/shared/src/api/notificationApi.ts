import type { AxiosInstance } from 'axios';
import type {
  NotificationItem,
  NotificationSubscribeRequest,
  NotificationUnsubscribeRequest,
  NotificationUnreadCount,
} from '../types/mobile';
import { API_PATHS } from '../utils/constants';

export const listNotifications = async (
  client: AxiosInstance,
  params?: { unread_only?: boolean; page?: number; limit?: number },
): Promise<{ notifications: NotificationItem[]; total: number; page: number }> => {
  const response = await client.get<{
    notifications: NotificationItem[];
    total: number;
    page: number;
  }>(API_PATHS.NOTIFICATIONS, { params });
  return response.data;
};

export const getUnreadCount = async (
  client: AxiosInstance,
): Promise<NotificationUnreadCount> => {
  const response = await client.get<NotificationUnreadCount>(
    `${API_PATHS.NOTIFICATIONS}/unread-count`,
  );
  return response.data;
};

export const markNotificationRead = async (
  client: AxiosInstance,
  notificationId: string,
): Promise<void> => {
  await client.put(`${API_PATHS.NOTIFICATIONS}/${notificationId}/read`);
};

export const markAllNotificationsRead = async (
  client: AxiosInstance,
): Promise<{ status: string; updated_count: number }> => {
  const response = await client.put<{ status: string; updated_count: number }>(
    `${API_PATHS.NOTIFICATIONS}/read-all`,
  );
  return response.data;
};

export const deleteNotification = async (
  client: AxiosInstance,
  notificationId: string,
): Promise<void> => {
  await client.delete(`${API_PATHS.NOTIFICATIONS}/${notificationId}`);
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

export const unsubscribeNotifications = async (
  client: AxiosInstance,
  data: NotificationUnsubscribeRequest,
): Promise<{ remaining_topics: string[] }> => {
  const response = await client.post<{ remaining_topics: string[] }>(
    `${API_PATHS.NOTIFICATIONS}/unsubscribe`,
    data,
  );
  return response.data;
};
