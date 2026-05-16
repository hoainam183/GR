import { useCallback, useRef, useState } from 'react';
import type { ImperativePanelHandle } from 'react-resizable-panels';

const STORAGE_KEY = 'sidebar:size';
const DEFAULT_SIZE = 22;
const MIN_SIZE = 16;
const MAX_SIZE = 32;

function clampSize(size: number): number {
  return Math.min(MAX_SIZE, Math.max(MIN_SIZE, size));
}

export function useResizableSidebar() {
  const panelRef = useRef<ImperativePanelHandle>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const toggle = useCallback(() => {
    const panel = panelRef.current;
    if (!panel) return;

    if (isCollapsed) {
      panel.expand();
    } else {
      panel.collapse();
    }
  }, [isCollapsed]);

  const onCollapse = useCallback(() => setIsCollapsed(true), []);
  const onExpand = useCallback(() => setIsCollapsed(false), []);

  const persistSize = useCallback((size: number) => {
    if (size > 0) {
      localStorage.setItem(STORAGE_KEY, String(clampSize(size)));
    }
  }, []);

  const getDefaultSize = useCallback((): number => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) return DEFAULT_SIZE;

    const parsed = Number(stored);
    return Number.isFinite(parsed) ? clampSize(parsed) : DEFAULT_SIZE;
  }, []);

  return {
    panelRef,
    isCollapsed,
    toggle,
    onCollapse,
    onExpand,
    persistSize,
    getDefaultSize,
  };
}
