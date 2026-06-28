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
let baseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim()?.replace(/\/$/, '') || 'http://localhost:8000';

if (Platform.OS === 'android' && baseUrl.includes('localhost')) {
  baseUrl = baseUrl.replace('localhost', '10.0.2.2');
}

export const API_BASE_URL = baseUrl;
