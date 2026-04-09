import { useState, useRef, useEffect, useCallback } from 'react';
import type { Message } from '@/types/chat';
import { sendMessage } from '@/services/chatApi';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import TypingIndicator from './TypingIndicator';

const ChatContainer = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  const handleSendMessage = async (content: string) => {
    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Build history from existing messages (last 6 turns)
      const historyForApi = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await sendMessage(content, historyForApi, 5, sessionId);

      // Persist session_id for subsequent turns in this conversation
      if (response.session_id && !sessionId) {
        setSessionId(response.session_id);
      }

      // Add assistant message with sources
      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
        sources: response.retrieved_documents,
        targetCollections: response.target_collections,
        collectionScores: response.collection_scores,
        reflectedQuestion: response.reflected_question,
        timingsMs: response.timings_ms,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to get response:', error);
      
      // Add error message
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: error instanceof Error 
          ? error.message 
          : 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 md:p-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <svg
                className="h-8 w-8 text-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <h3 className="mb-2 text-lg font-semibold text-foreground">
              Start a conversation
            </h3>
            <p className="max-w-sm text-sm text-muted-foreground">
              Ask me anything! I'm here to help with your questions.
            </p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-border bg-background/80 backdrop-blur-sm p-4 md:p-6">
        <div className="mx-auto max-w-3xl">
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
          <p className="mt-2 text-center text-xs text-muted-foreground">
            Press Enter to send, Shift + Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
};

export default ChatContainer;
