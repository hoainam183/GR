/**
 * Platform-agnostic chat store factory.
 *
 * Manages messages, active session, and chat phase (idle/thinking/streaming).
 */

import { createStore } from 'zustand/vanilla';
import type { Message } from '../types/chat';

export type ChatPhase = 'idle' | 'thinking' | 'streaming';

export interface ChatState {
  messages: Message[];
  activeSessionId: string | undefined;
  chatPhase: ChatPhase;

  addMessage: (message: Message) => void;
  updateMessage: (id: string, patch: Partial<Message>) => void;
  appendToMessage: (id: string, delta: string) => void;
  setMessages: (messages: Message[]) => void;
  setActiveSessionId: (sessionId: string | undefined) => void;
  setChatPhase: (phase: ChatPhase) => void;
  reset: () => void;
}

const INITIAL_STATE = {
  messages: [] as Message[],
  activeSessionId: undefined as string | undefined,
  chatPhase: 'idle' as ChatPhase,
};

export const createChatStore = () =>
  createStore<ChatState>((set) => ({
    ...INITIAL_STATE,

    addMessage: (message) =>
      set((state) => ({ messages: [...state.messages, message] })),

    updateMessage: (id, patch) =>
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === id ? { ...m, ...patch } : m,
        ),
      })),

    appendToMessage: (id, delta) =>
      set((state) => ({
        messages: state.messages.map((m) =>
          m.id === id ? { ...m, content: m.content + delta } : m,
        ),
      })),

    setMessages: (messages) => set({ messages }),

    setActiveSessionId: (sessionId) => set({ activeSessionId: sessionId }),

    setChatPhase: (phase) => set({ chatPhase: phase }),

    reset: () => set(INITIAL_STATE),
  }));

export type ChatStore = ReturnType<typeof createChatStore>;
