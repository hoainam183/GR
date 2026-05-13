/**
 * Chat screen — main conversation interface.
 *
 * Ported from web ChatContainer.tsx to React Native with:
 * - FlatList (inverted) for message list
 * - useStreamChat for SSE streaming via react-native-sse
 * - KeyboardAvoidingView for iOS keyboard handling
 * - Header with back navigation to SessionList
 */

import React, { useCallback, useRef, useEffect, useState } from 'react';
import {
  View,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  Pressable,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import type { ChatStackParamList } from '../../navigation/ChatStack';
import type { Message, ChatV3Response, RetrievedDocument } from '@rag/shared';
import { useStreamChat } from '../../hooks/useStreamChat';
import { useProfile } from '../../hooks/useProfile';
import { useChatStore } from '../../stores/chatStore';
import { useAuthStore } from '../../stores/authStore';
import { getSession, resolveChatIdentity } from '@rag/shared';
import { apiClient } from '../../services/api';
import MessageBubble from '../../components/chat/MessageBubble';
import ChatInput from '../../components/chat/ChatInput';
import TypingIndicator from '../../components/chat/TypingIndicator';
import SourceBottomSheet from '../../components/chat/SourceBottomSheet';
import LoadingSpinner from '../../components/common/LoadingSpinner';
import EmptyState from '../../components/common/EmptyState';

type Props = NativeStackScreenProps<ChatStackParamList, 'Chat'>;

const ChatScreen = ({ route, navigation }: Props) => {
  const sessionIdParam = route.params?.sessionId;
  const {
    messages,
    chatPhase,
    activeSessionId,
    addMessage,
    updateMessage,
    appendToMessage,
    setMessages,
    setActiveSessionId,
    setChatPhase,
    reset,
  } = useChatStore();

  const user = useAuthStore((s) => s.user);
  const { displayName } = useProfile();
  const { startStream, stopStream } = useStreamChat();
  const flatListRef = useRef<FlatList>(null);
  const isMountedRef = useRef(true);

  // State for sources bottom sheet
  const [selectedSources, setSelectedSources] = useState<RetrievedDocument[]>([]);
  const [sourcesVisible, setSourcesVisible] = useState(false);

  // Session title derived from first user message
  const [sessionTitle, setSessionTitle] = useState<string | null>(null);
  const insets = useSafeAreaInsets();

  // Track mount state
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      stopStream();
    };
  }, [stopStream]);

  // Load session history when sessionId changes
  useEffect(() => {
    if (!sessionIdParam) {
      reset();
      setSessionTitle(null);
      return;
    }

    setActiveSessionId(sessionIdParam);

    getSession(apiClient, sessionIdParam)
      .then(({ turns }) => {
        const loaded: Message[] = turns.flatMap((t) => [
          {
            id: `user-${t.turn_id}`,
            role: 'user' as const,
            content: t.question,
            timestamp: new Date(t.timestamp),
          },
          {
            id: `assistant-${t.turn_id}`,
            role: 'assistant' as const,
            content: t.answer,
            timestamp: new Date(t.timestamp),
            modelName: t.model_name,
            mode: t.mode,
            route: t.route ?? t.intent,
            toolsUsed: t.tools_used,
            timingsMs: t.timings_ms,
            sources: t.sources,
          },
        ]);
        if (isMountedRef.current) {
          setMessages(loaded);
          // Auto-generate title from first question
          if (turns.length > 0) {
            const firstQ = turns[0].question;
            setSessionTitle(
              firstQ.length > 40 ? firstQ.slice(0, 40) + '…' : firstQ,
            );
          }
        }
      })
      .catch((err) => {
        console.error('Failed to load session:', err);
      });
  }, [sessionIdParam]); // eslint-disable-line react-hooks/exhaustive-deps

  // ─── Source sheet handlers ──────────────────────────────────────────────────
  const handleShowSources = useCallback((sources: RetrievedDocument[]) => {
    setSelectedSources(sources);
    setSourcesVisible(true);
  }, []);

  const handleCloseSources = useCallback(() => {
    setSourcesVisible(false);
  }, []);

  // ─── Send message handler ─────────────────────────────────────────────────
  const handleSend = useCallback(
    async (content: string) => {
      const capturedSessionId = activeSessionId;

      // Add user message
      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date(),
      };
      addMessage(userMessage);
      setChatPhase('thinking');

      // Auto-set title from first question
      if (messages.length === 0 && !sessionTitle) {
        setSessionTitle(
          content.length > 40 ? content.slice(0, 40) + '…' : content,
        );
      }

      const assistantMessageId = `assistant-${Date.now()}`;
      let hasReceivedFirstToken = false;

      // Build history (last 6 messages)
      const historyForApi = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const identity = resolveChatIdentity(
        user
          ? {
              student_id: user.student_id,
              cohort: user.cohort,
              major: user.major,
              major_code: user.major_code,
              full_name: user.full_name,
            }
          : undefined,
        user?.email ?? user?.username ?? undefined,
      );

      try {
        await startStream(
          {
            question: content,
            history: historyForApi,
            top_k: 5,
            session_id: capturedSessionId,
            user_context: identity.userContext,
            user_id: identity.userId,
          },
          {
            onSessionId: (sid) => {
              if (!isMountedRef.current) return;
              setActiveSessionId(sid);
            },

            onToken: (delta) => {
              if (!isMountedRef.current) return;

              if (!hasReceivedFirstToken) {
                hasReceivedFirstToken = true;
                setChatPhase('streaming');
                addMessage({
                  id: assistantMessageId,
                  role: 'assistant',
                  content: delta,
                  timestamp: new Date(),
                  isStreaming: true,
                });
              } else {
                appendToMessage(assistantMessageId, delta);
              }
            },

            onMetadata: (meta: Partial<ChatV3Response>) => {
              if (!isMountedRef.current) return;
              updateMessage(assistantMessageId, {
                mode: meta.mode,
                route: meta.route ?? meta.intent,
                modelName: meta.model_name,
                timingsMs: meta.timings_ms,
                sources: meta.retrieved_documents,
                isStreaming: false,
              });
            },

            onDone: () => {
              if (!isMountedRef.current) return;
              updateMessage(assistantMessageId, { isStreaming: false });
              setChatPhase('idle');
            },

            onError: (error) => {
              if (!isMountedRef.current) return;
              if (!hasReceivedFirstToken) {
                addMessage({
                  id: assistantMessageId,
                  role: 'assistant',
                  content: error || 'Đã xảy ra lỗi. Vui lòng thử lại.',
                  timestamp: new Date(),
                  error,
                });
              }
              setChatPhase('idle');
            },
          },
        );
      } catch (error) {
        if (isMountedRef.current) {
          addMessage({
            id: `error-${Date.now()}`,
            role: 'assistant',
            content:
              error instanceof Error
                ? error.message
                : 'Đã xảy ra lỗi. Vui lòng thử lại.',
            timestamp: new Date(),
          });
          setChatPhase('idle');
        }
      }
    },
    [
      activeSessionId,
      messages,
      sessionTitle,
      user,
      startStream,
      addMessage,
      updateMessage,
      appendToMessage,
      setChatPhase,
      setActiveSessionId,
    ],
  );

  // ─── Render ────────────────────────────────────────────────────────────────

  const renderMessage = useCallback(
    ({ item }: { item: Message }) => (
      <MessageBubble
        message={item}
        onShowSources={handleShowSources}
      />
    ),
    [handleShowSources],
  );

  const greeting = displayName
    ? `Xin chào, ${displayName}!`
    : 'Bắt đầu trò chuyện';

  const renderEmptyState = () => (
    <EmptyState
      icon="chatbubbles"
      title={greeting}
      subtitle="Tôi có thể tư vấn về quy chế học tập, học bổng và các quy định của BKHN."
    />
  );

  const headerTitle = sessionTitle ?? 'HUST Assistant';
  const reversedMessages = [...messages].reverse();

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable
          style={styles.headerBackButton}
          onPress={() => navigation.goBack()}
        >
          <Ionicons name="chevron-back" size={24} color="#94a3b8" />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {headerTitle}
        </Text>
        <Pressable
          style={styles.headerAction}
          onPress={() => {
            reset();
            navigation.replace('Chat', undefined);
          }}
        >
          <Ionicons name="create-outline" size={22} color="#94a3b8" />
        </Pressable>
      </View>

      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={Platform.OS === 'ios' ? insets.top + 45 : 0}
      >
        {/* Messages */}
        {messages.length === 0 ? (
          renderEmptyState()
        ) : (
          <FlatList
            ref={flatListRef}
            style={styles.flex}
            data={reversedMessages}
            renderItem={renderMessage}
            keyExtractor={(item) => item.id}
            contentContainerStyle={styles.messageList}
            inverted={true}
            showsVerticalScrollIndicator={false}
            ListHeaderComponent={
              chatPhase !== 'idle' &&
              !messages[messages.length - 1]?.isStreaming ? (
                <TypingIndicator
                  phase={chatPhase as 'thinking' | 'streaming'}
                />
              ) : null
            }
          />
        )}

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={chatPhase !== 'idle'} />
      </KeyboardAvoidingView>

      {/* Source Bottom Sheet */}
      <SourceBottomSheet
        sources={selectedSources}
        visible={sourcesVisible}
        onClose={handleCloseSources}
      />
    </SafeAreaView>
  );
};



const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  flex: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 4,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#1e293b',
    backgroundColor: '#0f172a',
    gap: 4,
  },
  headerBackButton: {
    padding: 8,
  },
  headerTitle: {
    flex: 1,
    fontSize: 17,
    fontWeight: '600',
    color: '#f8fafc',
    textAlign: 'center',
  },
  headerAction: {
    padding: 8,
  },
  messageList: {
    paddingVertical: 16,
  },

});

export default ChatScreen;
