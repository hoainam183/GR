/**
 * Profile hook — fetch and manage user profile data.
 */

import { useAuthStore } from '../stores/authStore';

export const useProfile = () => {
  const user = useAuthStore((s) => s.user);

  const displayName = user?.full_name
    ? user.full_name.split(' ').pop() ?? user.full_name
    : null;

  const subtitle = [
    user?.major,
    user?.cohort ? `Khoá ${user.cohort}` : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return {
    user,
    displayName,
    subtitle,
    studentId: user?.student_id ?? null,
    majorCode: user?.major_code ?? null,
  };
};
