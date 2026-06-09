import React, { useCallback, useRef, useEffect, useState, useMemo } from "react";
import {
  View,
  FlatList,
  KeyboardAvoidingView,
  Keyboard,
  Platform,
  StyleSheet,
  Text,
  Pressable,
  ScrollView,
  type NativeSyntheticEvent,
  type NativeScrollEvent,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useNetInfo } from "@react-native-community/netinfo";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { ChatStackParamList } from "../../navigation/ChatStack";
import type { ChatV3Response, Message, RetrievedDocument, SuggestedQuestion } from "@rag/shared";
import { useQuery } from "@tanstack/react-query";
import { useStreamChat } from "../../hooks/useStreamChat";
import { useProfile } from "../../hooks/useProfile";
import { useChatStore } from "../../stores/chatStore";
import { getSession, getSuggestedQuestions, normalizeRetrievedDocuments } from "@rag/shared";
import { apiClient } from "../../services/api";
import { CACHE_KEYS, getCache, setCache } from "../../services/offlineCache";
import MessageBubble from "../../components/chat/MessageBubble";
import ChatInput from "../../components/chat/ChatInput";
import TypingIndicator from "../../components/chat/TypingIndicator";
import SourceBottomSheet from "../../components/chat/SourceBottomSheet";
import EmptyState from "../../components/common/EmptyState";
import { useAppTheme, type AppColors } from "../../theme/theme";

type Props = NativeStackScreenProps<ChatStackParamList, "Chat">;
const HEADER_HEIGHT = 60;

const ChatScreen = ({ route, navigation }: Props) => {
  const { colors } = useAppTheme();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const sessionIdParam = route.params?.sessionId;
  const { messages, chatPhase, activeSessionId, addMessage, updateMessage, appendToMessage,
    setMessages, setActiveSessionId, setChatPhase, reset } = useChatStore();
  const { displayName } = useProfile();
  const { startStream, stopStream } = useStreamChat();
  const netInfo = useNetInfo();
  const flatListRef = useRef<FlatList>(null);
  const isMountedRef = useRef(true);
  // Token batching (B3): buffer deltas, flush ~50ms to cut re-renders per token.
  const tokenBufferRef = useRef("");
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [selectedSources, setSelectedSources] = useState<RetrievedDocument[]>([]);
  const [sourcesVisible, setSourcesVisible] = useState(false);
  const [keyboardVisible, setKeyboardVisible] = useState(false);
  const [showScrollDown, setShowScrollDown] = useState(false);
  const [sessionTitle, setSessionTitle] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const insets = useSafeAreaInsets();
  const keyboardVerticalOffset = Platform.OS === "ios" ? insets.top + HEADER_HEIGHT : 0;

  const { data: suggestions = [] } = useQuery({
    queryKey: ["chat-suggestions"],
    queryFn: async () => {
      const result = await getSuggestedQuestions(apiClient);
      setCache(CACHE_KEYS.suggestions, result);
      return result;
    },
    initialData: () => getCache<SuggestedQuestion[]>(CACHE_KEYS.suggestions),
    staleTime: 10 * 60 * 1000,
  });

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (flushTimerRef.current) { clearTimeout(flushTimerRef.current); flushTimerRef.current = null; }
      tokenBufferRef.current = "";
      stopStream();
    };
  }, [stopStream]);

  useEffect(() => {
    const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow";
    const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide";
    const showSub = Keyboard.addListener(showEvent, () => {
      setKeyboardVisible(true);
      flatListRef.current?.scrollToOffset({ offset: 0, animated: true });
    });
    const hideSub = Keyboard.addListener(hideEvent, () => { setKeyboardVisible(false); });
    return () => { showSub.remove(); hideSub.remove(); };
  }, []);

  useEffect(() => {
    if (!sessionIdParam) { reset(); setSessionTitle(null); return; }
    setActiveSessionId(sessionIdParam);
    getSession(apiClient, sessionIdParam)
      .then(({ turns }) => {
        const loaded: Message[] = turns.flatMap((t) => [
          { id: "user-" + t.turn_id, role: "user" as const, content: t.question, timestamp: new Date(t.timestamp) },
          { id: "assistant-" + t.turn_id, role: "assistant" as const, content: t.answer,
            timestamp: new Date(t.timestamp), sessionId: sessionIdParam, turnId: t.turn_id,
            modelName: t.model_name, mode: t.mode, route: t.route ?? t.intent,
            toolsUsed: t.tools_used, timingsMs: t.timings_ms,
            sources: normalizeRetrievedDocuments(t.sources) },
        ]);
        if (isMountedRef.current) {
          setMessages(loaded);
          if (turns.length > 0) {
            const firstQ = turns[0].question;
            setSessionTitle(firstQ.length > 40 ? firstQ.slice(0, 40) + "..." : firstQ);
          }
        }
      })
      .catch(() => {
        if (isMountedRef.current) {
          addMessage({ id: "error-" + Date.now(), role: "assistant",
            content: "Không thể tải lịch sử hội thoại. Vui lòng thử lại sau.",
            timestamp: new Date(), error: "load_failed" });
        }
      });
  }, [sessionIdParam]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleShowSources = useCallback((sources: RetrievedDocument[]) => {
    setSelectedSources(sources); setSourcesVisible(true);
  }, []);
  const handleCloseSources = useCallback(() => { setSourcesVisible(false); }, []);

  const handleSend = useCallback(
    async (content: string) => {
      const capturedSessionId = activeSessionId;
      let currentSessionId = capturedSessionId;
      const online = netInfo.isConnected !== false && netInfo.isInternetReachable !== false;
      if (!online) {
        addMessage({ id: "offline-" + Date.now(), role: "assistant",
          content: "Bạn cần kết nối Internet để gửi câu hỏi mới.", timestamp: new Date(), error: "offline" });
        return;
      }
      addMessage({ id: "user-" + Date.now(), role: "user", content, timestamp: new Date() });
      setChatPhase("thinking");
      setStatusMessage(null);
      if (messages.length === 0 && !sessionTitle) {
        setSessionTitle(content.length > 40 ? content.slice(0, 40) + "..." : content);
      }
      const assistantMessageId = "assistant-" + Date.now();
      let hasReceivedFirstToken = false;
      const historyForApi = messages.slice(-6).map((m) => ({ role: m.role, content: m.content }));
      // Flush buffered tokens into the message in one update.
      const drainTokenBuffer = () => {
        if (flushTimerRef.current) { clearTimeout(flushTimerRef.current); flushTimerRef.current = null; }
        const buffered = tokenBufferRef.current;
        tokenBufferRef.current = "";
        if (buffered && isMountedRef.current) { appendToMessage(assistantMessageId, buffered); }
      };
      try {
        await startStream(
          { question: content, history: historyForApi, top_k: 7, session_id: capturedSessionId },
          {
            onSessionId: (sid) => { if (!isMountedRef.current) return; currentSessionId = sid; setActiveSessionId(sid); },
            onStatus: (s) => { if (isMountedRef.current) setStatusMessage(s.message); },
            onToken: (delta) => {
              if (!isMountedRef.current) return;
              if (!hasReceivedFirstToken) {
                hasReceivedFirstToken = true; setChatPhase("streaming"); setStatusMessage(null);
                addMessage({ id: assistantMessageId, role: "assistant", content: delta,
                  timestamp: new Date(), sessionId: currentSessionId, isStreaming: true });
                return;
              }
              // Buffer, then flush on a ~50ms timer to coalesce re-renders.
              tokenBufferRef.current += delta;
              if (flushTimerRef.current) return;
              flushTimerRef.current = setTimeout(drainTokenBuffer, 50);
            },
            onMetadata: (meta: Partial<ChatV3Response>) => {
              if (!isMountedRef.current) return;
              drainTokenBuffer();
              const sources = normalizeRetrievedDocuments(meta.retrieved_documents);
              updateMessage(assistantMessageId, { mode: meta.mode, route: meta.route ?? meta.intent,
                modelName: meta.model_name, timingsMs: meta.timings_ms, sources,
                sessionId: meta.session_id || currentSessionId, turnId: meta.turn_id, isStreaming: false });
            },
            onDone: () => {
              if (!isMountedRef.current) return;
              drainTokenBuffer();
              updateMessage(assistantMessageId, { isStreaming: false }); setChatPhase("idle"); setStatusMessage(null);
            },
            onError: (error) => {
              if (!isMountedRef.current) return;
              drainTokenBuffer();
              if (!hasReceivedFirstToken) {
                addMessage({ id: assistantMessageId, role: "assistant",
                  content: error || "Đã xảy ra lỗi. Vui lòng thử lại.", timestamp: new Date(), error });
              }
              setChatPhase("idle"); setStatusMessage(null);
            },
          },
        );
      } catch (error) {
        if (isMountedRef.current) {
          addMessage({ id: "error-" + Date.now(), role: "assistant",
            content: error instanceof Error ? error.message : "Đã xảy ra lỗi. Vui lòng thử lại.",
            timestamp: new Date() });
          setChatPhase("idle");
          setStatusMessage(null);
        }
      }
    },
    [activeSessionId, netInfo.isConnected, netInfo.isInternetReachable, messages, sessionTitle,
     startStream, addMessage, updateMessage, appendToMessage, setChatPhase, setActiveSessionId],
  );

  const renderMessage = useCallback(
    ({ item }: { item: Message }) => <MessageBubble message={item} onShowSources={handleShowSources} />,
    [handleShowSources],
  );
  const greeting = displayName ? "Xin chào, " + displayName + "!" : "Bắt đầu trò chuyện";
  const renderEmptyState = () => (
    <View style={styles.emptyWrap}>
      <EmptyState icon="chatbubbles" title={greeting}
        subtitle="Tôi có thể tư vấn về quy chế học tập, học bổng và các quy định của BKHN." />
      {!keyboardVisible && suggestions.length > 0 && (
        <ScrollView horizontal style={styles.suggestionScroll} showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.suggestionRow}>
          {suggestions.slice(0, 6).map((item) => (
            <Pressable key={item.question}
              style={[styles.suggestionChip, chatPhase !== "idle" && styles.suggestionChipDisabled]}
              onPress={() => handleSend(item.question)} disabled={chatPhase !== "idle"}>
              <Text style={styles.suggestionText} numberOfLines={1} ellipsizeMode="tail">
                {item.question}
              </Text>
            </Pressable>
          ))}
        </ScrollView>
      )}
    </View>
  );

  const headerTitle = sessionTitle ?? "HUST Assistant";
  const reversedMessages = useMemo(() => [...messages].reverse(), [messages]);
  const handleScroll = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => { setShowScrollDown(e.nativeEvent.contentOffset.y > 200); },
    [],
  );

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <View style={styles.header}>
        <Pressable style={styles.headerBackButton} onPress={() => navigation.goBack()}
          accessibilityLabel="Quay lại" accessibilityRole="button">
          <Ionicons name="chevron-back" size={24} color={colors.mutedForeground} />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>{headerTitle}</Text>
        <Pressable style={styles.headerAction}
          onPress={() => { reset(); navigation.replace("Chat", undefined); }}
          accessibilityLabel="Tạo hội thoại mới" accessibilityRole="button">
          <Ionicons name="create-outline" size={22} color={colors.mutedForeground} />
        </Pressable>
      </View>
      <KeyboardAvoidingView style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={keyboardVerticalOffset}>
        {messages.length === 0 ? renderEmptyState() : (
          <FlatList ref={flatListRef} style={styles.flex} data={reversedMessages}
            renderItem={renderMessage} keyExtractor={(item) => item.id}
            contentContainerStyle={styles.messageList} inverted={true}
            showsVerticalScrollIndicator={false} onScroll={handleScroll}
            scrollEventThrottle={100} maxToRenderPerBatch={10} windowSize={7}
            removeClippedSubviews={Platform.OS === "android"} initialNumToRender={15}
            ListHeaderComponent={
              chatPhase !== "idle" && !messages[messages.length - 1]?.isStreaming
                ? <TypingIndicator phase={chatPhase as "thinking" | "streaming"} label={statusMessage ?? undefined} />
                : null
            }
          />
        )}
        <ChatInput onSend={handleSend} onFocus={() => setKeyboardVisible(true)}
          bottomInset={insets.bottom}
          disabled={chatPhase !== "idle" || netInfo.isConnected === false || netInfo.isInternetReachable === false} />
      </KeyboardAvoidingView>
      {showScrollDown && (
        <Pressable style={styles.scrollDownButton}
          onPress={() => flatListRef.current?.scrollToOffset({ offset: 0, animated: true })}
          accessibilityLabel="Cuộn xuống cuối" accessibilityRole="button">
          <Ionicons name="chevron-down" size={20} color={colors.primaryForeground} />
        </Pressable>
      )}
      <SourceBottomSheet sources={selectedSources} visible={sourcesVisible} onClose={handleCloseSources} />
    </SafeAreaView>
  );
};

const createStyles = (colors: AppColors) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.canvas },
    flex: { flex: 1 },
    header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 4, paddingVertical: 10,
      borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.background, gap: 4 },
    headerBackButton: { padding: 8 },
    headerTitle: { flex: 1, fontSize: 17, fontWeight: "600", color: colors.foreground, textAlign: "center" },
    headerAction: { padding: 8 },
    messageList: { paddingVertical: 16 },
    emptyWrap: { flex: 1 },
    suggestionScroll: { flexGrow: 0, maxHeight: 50 },
    suggestionRow: { paddingHorizontal: 12, paddingTop: 2, paddingBottom: 10, gap: 8 },
    suggestionChip: { width: 156, height: 38, justifyContent: "center", backgroundColor: colors.card,
      borderWidth: 1, borderColor: colors.border, borderRadius: 19, paddingHorizontal: 12 },
    suggestionChipDisabled: { opacity: 0.5 },
    suggestionText: { color: colors.foreground, fontSize: 12, lineHeight: 16, fontWeight: "500" },
    scrollDownButton: { position: "absolute", bottom: 80, right: 20, width: 40, height: 40,
      borderRadius: 20, backgroundColor: colors.primary, justifyContent: "center", alignItems: "center",
      elevation: 4, shadowColor: "#000", shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.2, shadowRadius: 4 },
  });

export default ChatScreen;
