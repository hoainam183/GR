/**
 * Mobile app constants.
 */

import { Platform } from 'react-native';

/**
 * Base URL for the backend API.
 *
 * - Android emulator: `10.0.2.2` is the host machine's loopback
 * - iOS simulator:    `localhost` works directly
 * - Physical device:  replace with your machine's LAN IP
 */
const envBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();

export const API_BASE_URL =
  envBaseUrl?.replace(/\/$/, '') ||
  (Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000');
