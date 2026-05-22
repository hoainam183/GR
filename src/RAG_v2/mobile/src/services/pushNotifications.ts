import Constants from 'expo-constants';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import { getCache, setCache } from './offlineCache';

const PUSH_TOKEN_CACHE_KEY = 'notifications:expo-push-token:v1';
const PUSH_ENABLED_CACHE_KEY = 'notifications:push-enabled:v1';

export class PushPermissionDeniedError extends Error {
  constructor() {
    super('Push notification permission was not granted.');
    this.name = 'PushPermissionDeniedError';
  }
}

export const getStoredPushToken = (): string | null =>
  getCache<string | null>(PUSH_TOKEN_CACHE_KEY) ?? null;

export const isPushEnabledLocally = (): boolean =>
  getCache<boolean>(PUSH_ENABLED_CACHE_KEY) ?? false;

export const clearStoredPushRegistration = (): void => {
  setCache(PUSH_TOKEN_CACHE_KEY, null);
  setCache(PUSH_ENABLED_CACHE_KEY, false);
};

export const registerDeviceForPushNotifications = async (): Promise<string> => {
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'HUST Assistant',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }

  const current = await Notifications.getPermissionsAsync();
  const permission =
    current.status === 'granted'
      ? current
      : await Notifications.requestPermissionsAsync();
  if (permission.status !== 'granted') throw new PushPermissionDeniedError();

  const projectId =
    Constants.easConfig?.projectId ??
    (Constants.expoConfig?.extra?.eas as { projectId?: string } | undefined)?.projectId;
  const tokenResult = projectId
    ? await Notifications.getExpoPushTokenAsync({ projectId })
    : await Notifications.getExpoPushTokenAsync();

  setCache(PUSH_TOKEN_CACHE_KEY, tokenResult.data);
  setCache(PUSH_ENABLED_CACHE_KEY, true);
  return tokenResult.data;
};

