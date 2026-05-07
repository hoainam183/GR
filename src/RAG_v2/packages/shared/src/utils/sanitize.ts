/**
 * Text cleaning and sanitization utilities.
 * Extracted from frontend/chat-companion/src/services/chatApi.ts
 */

import type { UserContext } from '../types/chat';

/**
 * Trim a value to a clean string or undefined.
 */
export const cleanText = (value: unknown): string | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const cleaned = value.trim();
  return cleaned.length > 0 ? cleaned : undefined;
};

/**
 * Strip empty/whitespace-only fields from a UserContext.
 * Returns undefined if all fields are empty.
 */
export const sanitizeUserContext = (
  context?: UserContext,
): UserContext | undefined => {
  if (!context) {
    return undefined;
  }

  const cleaned: UserContext = {};
  const studentId = cleanText(context.student_id);
  const cohort = cleanText(context.cohort);
  const major = cleanText(context.major);
  const majorCode = cleanText(context.major_code);
  const fullName = cleanText(context.full_name);

  if (studentId) cleaned.student_id = studentId;
  if (cohort) cleaned.cohort = cohort;
  if (major) cleaned.major = major;
  if (majorCode) cleaned.major_code = majorCode;
  if (fullName) cleaned.full_name = fullName;

  return Object.keys(cleaned).length > 0 ? cleaned : undefined;
};
