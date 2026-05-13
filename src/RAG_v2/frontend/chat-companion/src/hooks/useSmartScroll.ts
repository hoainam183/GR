import { useState, useEffect, useCallback, RefObject } from 'react';

export function useSmartScroll(
  messagesEndRef: RefObject<HTMLDivElement>,
  dependencies: unknown[] = []
) {
  const [isNearBottom, setIsNearBottom] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Set up intersection observer to track if the bottom of the chat is visible
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsNearBottom(entry.isIntersecting);
        setShowScrollButton(!entry.isIntersecting);
      },
      {
        root: null, // viewport
        rootMargin: '100px', // Consider "near bottom" if within 100px of the end
        threshold: 0,
      }
    );

    const target = messagesEndRef.current;
    if (target) {
      observer.observe(target);
    }

    return () => {
      if (target) {
        observer.unobserve(target);
      }
    };
  }, [messagesEndRef]);

  // The auto-scroll function only triggers if user is already near bottom
  const smartScrollToBottom = useCallback(() => {
    if (isNearBottom && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [isNearBottom, messagesEndRef]);

  // A forced scroll for when user explicitly clicks down or sends a message
  const forceScrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messagesEndRef]);

  // Auto scroll when dependencies change (like message array), but respect isNearBottom
  useEffect(() => {
    smartScrollToBottom();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...dependencies, smartScrollToBottom]);

  return {
    showScrollButton,
    forceScrollToBottom,
    isNearBottom
  };
}
