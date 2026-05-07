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
export const API_BASE_URL = 'http://192.168.1.182:8000'; // IP LAN để test trên điện thoại thật
