/**
 * SSE streaming hook for mobile — uses react-native-sse (native EventSource).
 *
 * Web uses ReadableStream; this is the mobile equivalent.
 */

import EventSource from 'react-native-sse';
import { useCallback, useRef } from 'react';
import { getToken } from '../services/secureStorage';
import { API_BASE_URL } from '../utils/constants';
import { apiClient, refreshAccessToken } from '../services/api';
import type { ChatRequest, ChatV3Response } from '@rag/shared';
import { normalizeV3Response, cleanText, sendMessageV3 } from '@rag/shared';

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
      const openStream = async (retryOnAuthError: boolean) => {
        // Cleanup any previous stream
        esRef.current?.close();

      const token = (await getToken()) ?? (await refreshAccessToken().catch(() => null));
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

      let receivedFirstToken = false;
      let finished = false;

      const fallbackToNonStreaming = async (message?: string) => {
        if (finished || receivedFirstToken) return;
        finished = true;
        es.close();
        try {
          const response = await sendMessageV3(
            apiClient,
            request.question,
            request.history ?? [],
            request.top_k ?? 5,
            request.mode ?? 'auto',
            request.session_id,
            request.user_context,
            request.user_id,
          );
          if (response.session_id) handlers.onSessionId?.(response.session_id);
          if (response.answer) handlers.onToken?.(response.answer);
          handlers.onMetadata?.(response);
          handlers.onDone?.();
        } catch (error) {
          handlers.onError?.(
            error instanceof Error
              ? error.message
              : message || 'Connection lost',
          );
        }
      };

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
              receivedFirstToken = true;
              handlers.onToken?.(delta);
            }
          } else if (type === 'metadata') {
            const meta = normalizeV3Response(data, request.session_id);
            handlers.onMetadata?.(meta);
          } else if (type === 'done') {
            finished = true;
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
          receivedFirstToken = true;
          handlers.onToken?.(event.data);
        }
      });

      es.addEventListener('error', (event) => {
        const message = (event as { message?: string }).message || 'Connection lost';
        if (!receivedFirstToken) {
          if (retryOnAuthError) {
            void refreshAccessToken()
              .then((refreshed) => {
                if (refreshed) {
                  void openStream(false);
                } else {
                  void fallbackToNonStreaming(message);
                }
              })
              .catch(() => {
                void fallbackToNonStreaming(message);
              });
            return;
          }
          void fallbackToNonStreaming(message);
          return;
        }
        finished = true;
        handlers.onError?.(message);
        es.close();
      });
      };

      await openStream(true);
    },
    [],
  );

  const stopStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  return { startStream, stopStream };
};
