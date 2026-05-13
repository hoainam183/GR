/**
 * Mobile chat store — wraps the shared createChatStore with React hooks.
 */

import { useStore } from 'zustand';
import { createChatStore, type ChatState } from '@rag/shared';

export const chatStore = createChatStore();

// ─── React hook wrapper ──────────────────────────────────────────────────────

export function useChatStore(): ChatState;
export function useChatStore<T>(selector: (state: ChatState) => T): T;
export function useChatStore<T>(selector?: (state: ChatState) => T) {
  return useStore(chatStore, selector!);
}
