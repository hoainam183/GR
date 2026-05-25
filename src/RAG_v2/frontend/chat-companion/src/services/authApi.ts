import axios from 'axios';
import {
  authFetch,
  installAuthInterceptors,
  throwIfNotOk,
} from '@/services/authSession';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

installAuthInterceptors(apiClient);

export interface RegisterRequest {
  username: string;
  password: string;
  full_name: string;
  student_id: string;
  cohort: string;
  major: string;
  major_code: string;
}

export interface UserPublic {
  _id?: string;
  username?: string | null;
  email?: string | null;
  full_name: string;
  student_id: string;
  cohort: string;
  major: string;
  major_code: string;
  role?: string;
  is_profile_complete: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
  client_type?: 'web' | 'mobile';
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserPublic;
  refresh_token?: string | null;
}

export const registerUser = async (data: RegisterRequest): Promise<UserPublic> => {
  const response = await apiClient.post<UserPublic>('/auth/register', data);
  return response.data;
};

export const loginUser = async (data: LoginRequest): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>('/auth/login', {
    ...data,
    client_type: data.client_type ?? 'web',
  });
  return response.data;
};

export const getMe = async (token?: string): Promise<UserPublic> => {
  if (token) {
    const response = await apiClient.get<UserPublic>('/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    return response.data;
  }

  const response = await authFetch('/auth/me');
  await throwIfNotOk(response, 'Failed to load current user.');
  return (await response.json()) as UserPublic;
};
