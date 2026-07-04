import { useState, useEffect, useCallback, RefObject } from 'react';

export function useSmartScroll(
  messagesEndRef: RefObject<HTMLDivElement>,
  dependencies: unknown[] = [],
  scrollContainerRef?: RefObject<HTMLElement>,
  isStreaming = false
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
        root: scrollContainerRef?.current ?? null,
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
  }, [messagesEndRef, scrollContainerRef]);

  const scrollToBottom = useCallback(
    (behavior: ScrollBehavior) => {
      const container = scrollContainerRef?.current;
      if (container) {
        container.scrollTo({
          top: container.scrollHeight,
          behavior,
        });
        return;
      }

      messagesEndRef.current?.scrollIntoView({ behavior, block: 'end' });
    },
    [messagesEndRef, scrollContainerRef],
  );

  // The auto-scroll function only triggers if user is already near bottom.
  // While streaming we pin to the bottom with 'auto' (instant) so we don't stack
  // a fresh smooth-scroll animation on every token flush — that stacking is what
  // makes the view stutter during a response.
  const smartScrollToBottom = useCallback(() => {
    if (isNearBottom) {
      scrollToBottom(isStreaming ? 'auto' : 'smooth');
    }
  }, [isNearBottom, scrollToBottom, isStreaming]);

  // A forced scroll for when user explicitly clicks down or sends a message
  const forceScrollToBottom = useCallback(() => {
    scrollToBottom('smooth');
  }, [scrollToBottom]);

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
