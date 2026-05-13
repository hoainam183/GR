/**
 * Authentication API functions — platform-agnostic.
 */

import type { AxiosInstance } from 'axios';
import type {
  RegisterRequest,
  LoginRequest,
  TokenResponse,
  UserPublic,
} from '../types/auth';
import { API_PATHS } from '../utils/constants';

/**
 * Register a new user — POST /auth/register
 */
export const registerUser = async (
  client: AxiosInstance,
  data: RegisterRequest,
): Promise<UserPublic> => {
  const response = await client.post<UserPublic>(API_PATHS.AUTH_REGISTER, data);
  return response.data;
};

/**
 * Login — POST /auth/login
 */
export const loginUser = async (
  client: AxiosInstance,
  data: LoginRequest,
): Promise<TokenResponse> => {
  const response = await client.post<TokenResponse>(API_PATHS.AUTH_LOGIN, data);
  return response.data;
};

/**
 * Get current user profile — GET /auth/me
 */
export const getMe = async (
  client: AxiosInstance,
  token: string,
): Promise<UserPublic> => {
  const response = await client.get<UserPublic>(API_PATHS.AUTH_ME, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return response.data;
};
