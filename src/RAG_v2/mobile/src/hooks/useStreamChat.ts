/**
 * SSE streaming hook for mobile — uses react-native-sse (native EventSource).
 *
 * Web uses ReadableStream; this is the mobile equivalent.
 */

import EventSource from 'react-native-sse';
import { useCallback, useRef } from 'react';
import { getToken } from '../services/secureStorage';
import { API_BASE_URL } from '../utils/constants';
import type { ChatRequest, ChatV3Response, UserContext } from '@rag/shared';
import { normalizeV3Response, cleanText } from '@rag/shared';

export interface StreamChatHandlers {
  onSessionId?: (sessionId: string) => void;
  onToken?: (delta: string) => void;
  onMetadata?: (meta: Partial<ChatV3Response>) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

export const useStreamChat = () => {
  const esRef = useRef<EventSource | null>(null);

  const startStream = useCallback(
    async (request: ChatRequest, handlers: StreamChatHandlers = {}) => {
      // Cleanup any previous stream
      esRef.current?.close();

      const token = await getToken();
      const url = `${API_BASE_URL}/chat/stream`;

      const es = new EventSource<'message' | 'error'>(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(request),
      });
      esRef.current = es;

      let buffer = '';

      es.addEventListener('message', (event) => {
        if (!event.data) return;

        try {
          const data = JSON.parse(event.data) as Record<string, unknown>;
          const type = typeof data.type === 'string' ? data.type : '';

          if (type === 'session') {
            const sid = cleanText(data.session_id);
            if (sid) handlers.onSessionId?.(sid);
          } else if (type === 'token') {
            const delta =
              typeof data.delta === 'string' ? data.delta : '';
            if (delta) {
              buffer += delta;
              handlers.onToken?.(delta);
            }
          } else if (type === 'metadata') {
            const meta = normalizeV3Response(data);
            handlers.onMetadata?.(meta);
          } else if (type === 'done') {
            handlers.onDone?.();
            es.close();
          } else if (type === 'error') {
            handlers.onError?.(
              typeof data.error === 'string'
                ? data.error
                : 'Unknown stream error',
            );
            es.close();
          }
        } catch {
          // Plain text token fallback
          buffer += event.data;
          handlers.onToken?.(event.data);
        }
      });

      es.addEventListener('error', (event) => {
        handlers.onError?.(
          (event as { message?: string }).message || 'Connection lost',
        );
        es.close();
      });
    },
    [],
  );

  const stopStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  return { startStream, stopStream };
};
