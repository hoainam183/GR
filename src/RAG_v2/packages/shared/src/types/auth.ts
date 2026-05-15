/**
 * Authentication types — shared between web and mobile.
 * Extracted from frontend/chat-companion/src/services/authApi.ts
 */

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
  id?: string;
  _id?: string;
  username?: string | null;
  email?: string | null;
  full_name: string;
  student_id: string;
  cohort: string;
  major: string;
  major_code: string;
  is_profile_complete: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: UserPublic;
}

export const normalizeUser = (user: UserPublic): UserPublic => ({
  ...user,
  id: user.id ?? user._id,
});
