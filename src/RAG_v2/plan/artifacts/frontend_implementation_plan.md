# Refactor UI/UX Chat-Companion — ChatGPT-style

> Thêm backend API + Frontend: delete chat, rename chat, resizable sidebar, ChatGPT UX.

---

## Phase 1 — Backend: Delete & Rename Session APIs

### [MODIFY] [mongo_logger.py](file:///d:/GR/src/RAG_v2/models/mongo_logger.py)

Thêm 2 methods sau vào class `MongoLogger` (sau `list_sessions`, ~line 81):

```python
def delete_session(self, session_id: str) -> bool:
    """Delete session + all turns + query_logs."""
    result = self._sessions.delete_one({"session_id": session_id})
    self._turns.delete_many({"session_id": session_id})
    self._query_logs.delete_many({"session_id": session_id})
    self._agent_traces.delete_many({"session_id": session_id})
    return result.deleted_count > 0

def update_session_title(self, session_id: str, title: str) -> bool:
    """Update the title of a session."""
    result = self._sessions.update_one(
        {"session_id": session_id},
        {"$set": {"title": title}},
    )
    return result.modified_count > 0
```

---

### [MODIFY] [session_store.py](file:///d:/GR/src/RAG_v2/cache/session_store.py)

Thêm 2 methods vào class `RedisSessionStore` (sau `update_session_on_turn`, ~line 227):

```python
def delete_session(self, session_id: str) -> bool:
    """Delete session from Redis + MongoDB (dual-write)."""
    key = f"session:{session_id}"
    try:
        user_id = self._r.hget(key, "user_id")
        pipe = self._r.pipeline()
        pipe.delete(key)
        if user_id:
            pipe.zrem(f"user_sessions:{user_id}", session_id)
        pipe.execute()
    except redis.RedisError:
        logger.warning("Redis delete_session failed", exc_info=True)

    if self._mongo:
        return self._mongo.delete_session(session_id)
    return True

def update_session_title(self, session_id: str, title: str) -> bool:
    """Update title in Redis + MongoDB."""
    key = f"session:{session_id}"
    try:
        self._r.hset(key, "title", title)
    except redis.RedisError:
        logger.warning("Redis update_session_title failed", exc_info=True)

    if self._mongo:
        return self._mongo.update_session_title(session_id, title)
    return True
```

---

### [MODIFY] [session.py](file:///d:/GR/src/RAG_v2/api/routes/session.py)

Thêm 2 endpoints mới (append sau `list_my_sessions`, ~line 149):

```python
class SessionUpdateRequest(BaseModel):
    title: str


@router.delete("/{session_id}")
async def delete_session(
    request: Request,
    session_id: str,
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
):
    """Delete a session and all its associated data."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    # Verify ownership
    session = None
    if redis_session:
        session = redis_session.get_session(session_id)
    if session is None and mongo_logger:
        session = mongo_logger.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if current_user and session.get("user_id") not in (None, str(current_user.id)):
        raise HTTPException(status_code=404, detail="Session not found")

    if redis_session:
        redis_session.delete_session(session_id)
    elif mongo_logger:
        mongo_logger.delete_session(session_id)
    else:
        raise HTTPException(status_code=503, detail="No session store available")

    return {"deleted": True}


@router.patch("/{session_id}")
async def update_session(
    request: Request,
    session_id: str,
    body: SessionUpdateRequest,
    current_user: Annotated[
        UserDocument | None,
        Depends(get_optional_current_user),
    ] = None,
):
    """Update session metadata (title)."""
    redis_session = getattr(request.app.state, "redis_session", None)
    mongo_logger = getattr(request.app.state, "mongo_logger", None)

    # Verify ownership
    session = None
    if redis_session:
        session = redis_session.get_session(session_id)
    if session is None and mongo_logger:
        session = mongo_logger.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if current_user and session.get("user_id") not in (None, str(current_user.id)):
        raise HTTPException(status_code=404, detail="Session not found")

    title = body.title.strip()[:120]
    if redis_session:
        redis_session.update_session_title(session_id, title)
    elif mongo_logger:
        mongo_logger.update_session_title(session_id, title)
    else:
        raise HTTPException(status_code=503, detail="No session store available")

    return {"updated": True, "title": title}
```

---

## Phase 2 — Frontend: Session API

### [MODIFY] [sessionApi.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/services/sessionApi.ts)

Append 2 functions (sau `createSession`, ~line 38):

```typescript
export const deleteSession = async (sessionId: string): Promise<void> => {
  await apiClient.delete(`/session/${sessionId}`);
};

export const renameSession = async (
  sessionId: string,
  title: string,
): Promise<{ updated: boolean; title: string }> => {
  const response = await apiClient.patch<{ updated: boolean; title: string }>(
    `/session/${sessionId}`,
    { title },
  );
  return response.data;
};
```

---

## Phase 3 — Sidebar: ChatGPT-style Rewrite

### [MODIFY] [ConversationSidebar.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/sidebar/ConversationSidebar.tsx)

**Full rewrite** — 121 lines → ~280 lines. Key changes:

**3a. Imports thêm:**
```typescript
import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { MoreHorizontal, Pencil, Trash2, Plus, Search, MessageSquare, LogOut } from 'lucide-react';
import { deleteSession, renameSession } from '@/services/sessionApi';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
```

**3b. Props mở rộng:**
```typescript
interface ConversationSidebarProps {
  userId: string | null | undefined;
  onLogout: () => void;
  isMobile?: boolean;          // NEW: để biết context render
  onCloseMobile?: () => void;  // NEW: close Sheet khi navigate
}
```

**3c. Thêm function nhóm conversations theo thời gian:**
```typescript
function groupSessionsByDate(sessions: Session[]) {
  const now = Date.now();
  const DAY = 86_400_000;
  const groups: { label: string; sessions: Session[] }[] = [];
  const buckets = {
    'Hôm nay': [] as Session[],
    'Hôm qua': [] as Session[],
    '7 ngày trước': [] as Session[],
    '30 ngày trước': [] as Session[],
    'Cũ hơn': [] as Session[],
  };
  for (const s of sessions) {
    const diff = now - parseUtcDate(s.updated_at).getTime();
    if (diff < DAY) buckets['Hôm nay'].push(s);
    else if (diff < 2 * DAY) buckets['Hôm qua'].push(s);
    else if (diff < 7 * DAY) buckets['7 ngày trước'].push(s);
    else if (diff < 30 * DAY) buckets['30 ngày trước'].push(s);
    else buckets['Cũ hơn'].push(s);
  }
  for (const [label, items] of Object.entries(buckets)) {
    if (items.length > 0) groups.push({ label, sessions: items });
  }
  return groups;
}
```

**3d. State mới trong component:**
```typescript
const [searchQuery, setSearchQuery] = useState('');
const [editingId, setEditingId] = useState<string | null>(null);
const [editTitle, setEditTitle] = useState('');
const [deleteTarget, setDeleteTarget] = useState<Session | null>(null);
const editInputRef = useRef<HTMLInputElement>(null);
```

**3e. Mutations:**
```typescript
const renameMutation = useMutation({
  mutationFn: ({ id, title }: { id: string; title: string }) => renameSession(id, title),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['sessions', userId] });
    setEditingId(null);
  },
});

const deleteMutation = useMutation({
  mutationFn: (id: string) => deleteSession(id),
  onSuccess: (_data, deletedId) => {
    queryClient.invalidateQueries({ queryKey: ['sessions', userId] });
    setDeleteTarget(null);
    if (deletedId === activeSessionId) navigate('/chat');
  },
});
```

**3f. Search filter + grouped list:**
```typescript
const filtered = sessions.filter((s) =>
  !searchQuery || (s.title ?? '').toLowerCase().includes(searchQuery.toLowerCase()),
);
const groups = groupSessionsByDate(filtered);
```

**3g. Mỗi conversation item có hover actions:**
- Hover → hiển thị nút `⋯` (MoreHorizontal)
- Click `⋯` → `DropdownMenu` với "Đổi tên" + "Xoá"
- "Đổi tên" → `setEditingId(session.session_id)` → title thành `<input>`
  - Enter → `renameMutation.mutate()`
  - Escape → `setEditingId(null)`
- "Xoá" → `setDeleteTarget(session)` → mở `AlertDialog`

**3h. Search input ở header:**
```tsx
<div className="relative">
  <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
  <input
    value={searchQuery}
    onChange={(e) => setSearchQuery(e.target.value)}
    placeholder="Tìm kiếm..."
    className="h-8 w-full rounded-md border border-border bg-background pl-8 pr-3 text-xs
               placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
  />
</div>
```

**3i. AlertDialog cho delete:**
```tsx
<AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Xoá cuộc trò chuyện?</AlertDialogTitle>
      <AlertDialogDescription>
        "{deleteTarget?.title || 'Cuộc trò chuyện mới'}" sẽ bị xoá vĩnh viễn.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Huỷ</AlertDialogCancel>
      <AlertDialogAction
        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
        onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.session_id)}
      >
        Xoá
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

**3j. Component không còn wrap trong shadcn `<Sidebar>`** — render raw `div` structure:
```tsx
return (
  <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
    {/* Header: New Chat + Search */}
    <div className="shrink-0 space-y-2 px-3 py-3"> ... </div>
    {/* Grouped conversation list */}
    <div className="flex-1 overflow-y-auto scrollbar-thin px-2"> ... </div>
    {/* Footer: Logout */}
    <div className="shrink-0 border-t border-sidebar-border px-3 py-2"> ... </div>
    {/* Delete dialog (portaled) */}
    <AlertDialog ...> ... </AlertDialog>
  </div>
);
```

---

## Phase 4 — Resizable Sidebar Layout

### [NEW] [useResizableSidebar.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/hooks/useResizableSidebar.ts)

```typescript
import { useCallback, useRef, useState } from 'react';
import type { ImperativePanelHandle } from 'react-resizable-panels';

const STORAGE_KEY = 'sidebar:size';
const DEFAULT_SIZE = 20; // % of viewport

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
    if (size > 0) localStorage.setItem(STORAGE_KEY, String(size));
  }, []);

  const getDefaultSize = useCallback((): number => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? Number(stored) : DEFAULT_SIZE;
  }, []);

  return { panelRef, isCollapsed, toggle, onCollapse, onExpand, persistSize, getDefaultSize };
}
```

---

### [MODIFY] [Index.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/Index.tsx)

**Major layout rewrite.** Key changes:

**4a. Thay imports:**
```diff
-import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
+import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from '@/components/ui/resizable';
+import { Sheet, SheetContent } from '@/components/ui/sheet';
+import { useIsMobile } from '@/hooks/use-mobile';
+import { useResizableSidebar } from '@/hooks/useResizableSidebar';
+import { PanelLeft } from 'lucide-react';
+import { Button } from '@/components/ui/button';
```

**4b. Trong component `Index`, thêm state:**
```typescript
const isMobile = useIsMobile();
const [mobileOpen, setMobileOpen] = useState(false);
const { panelRef, isCollapsed, toggle, onCollapse, onExpand, persistSize, getDefaultSize }
  = useResizableSidebar();
```

**4c. Keyboard shortcut Ctrl+B:**
```typescript
useEffect(() => {
  const handler = (e: KeyboardEvent) => {
    if (e.key === 'b' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      if (isMobile) setMobileOpen((v) => !v);
      else toggle();
    }
  };
  window.addEventListener('keydown', handler);
  return () => window.removeEventListener('keydown', handler);
}, [isMobile, toggle]);
```

**4d. Header thay đổi:**
- Bỏ `SidebarTrigger`, thay bằng `Button ghost` gọi `toggle()` / `setMobileOpen(true)`
- Hiển thị tên conversation hiện tại thay vì "HUST Assistant" hardcoded (giữ logo)
- Bỏ "Đang hoạt động" status dot

**4e. Layout return — Desktop:**
```tsx
// Không còn SidebarProvider wrapper
<div className="flex h-screen w-full overflow-hidden bg-chat-container">
  {isMobile ? (
    <>
      {/* Mobile: Sheet overlay */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-[18rem] p-0 [&>button]:hidden">
          <ConversationSidebar
            userId={...} onLogout={handleLogout}
            isMobile onCloseMobile={() => setMobileOpen(false)}
          />
        </SheetContent>
      </Sheet>
      <main className="flex flex-1 flex-col overflow-hidden">
        <header>...</header>
        <div className="flex-1 overflow-hidden">
          <ChatContainer user={user} sessionId={sessionId} />
        </div>
      </main>
    </>
  ) : (
    <ResizablePanelGroup direction="horizontal" className="h-full">
      <ResizablePanel
        ref={panelRef}
        defaultSize={getDefaultSize()}
        minSize={15}
        maxSize={30}
        collapsible
        collapsedSize={0}
        onCollapse={onCollapse}
        onExpand={onExpand}
        onResize={persistSize}
        className="border-r border-border"
      >
        <ConversationSidebar userId={...} onLogout={handleLogout} />
      </ResizablePanel>

      <ResizableHandle className="w-1 bg-transparent hover:bg-primary/20 transition-colors" />

      <ResizablePanel defaultSize={80} minSize={50}>
        <main className="flex h-full flex-col overflow-hidden">
          <header>...</header>
          <div className="flex-1 overflow-hidden">
            <ChatContainer user={user} sessionId={sessionId} />
          </div>
        </main>
      </ResizablePanel>
    </ResizablePanelGroup>
  )}
</div>
```

---

## Phase 5 — Empty State: Suggestion Chips

### [MODIFY] [ChatContainer.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/chat/ChatContainer.tsx)

Thay phần `messages.length === 0` (lines 277-306) bằng:

```tsx
const SUGGESTIONS = [
  { icon: '📋', label: 'Quy chế đào tạo', query: 'Quy chế đào tạo tín chỉ mới nhất của BKHN là gì?' },
  { icon: '📚', label: 'CTDT ngành tôi', query: `Chương trình đào tạo ngành ${user?.major || 'của tôi'} gồm những gì?` },
  { icon: '💰', label: 'Chính sách học bổng', query: 'Các loại học bổng hiện có tại BKHN?' },
  { icon: '📅', label: 'Lịch học kỳ mới', query: 'Lịch trình học kỳ mới nhất?' },
];
```

Render:
```tsx
<div className="flex h-full flex-col items-center justify-center text-center px-4">
  {/* Logo + Greeting */}
  <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
    <Bot className="h-8 w-8 text-primary" />
  </div>
  <h3 className="mb-1 text-xl font-semibold text-foreground">{greeting}</h3>
  <p className="mb-8 max-w-md text-sm text-muted-foreground">
    Tôi có thể tư vấn về quy chế, CTDT, học bổng và các quy định của BKHN.
  </p>

  {/* Suggestion grid */}
  <div className="grid w-full max-w-lg grid-cols-2 gap-3">
    {SUGGESTIONS.map((s) => (
      <button
        key={s.label}
        onClick={() => handleSendMessage(s.query)}
        className="flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-left
                   transition-all hover:bg-secondary hover:shadow-sm"
      >
        <span className="text-xl">{s.icon}</span>
        <span className="text-sm font-medium text-foreground">{s.label}</span>
      </button>
    ))}
  </div>
</div>
```

Import thêm `Bot` từ `lucide-react`.

---

## Phase 6 — CSS Additions

### [MODIFY] [index.css](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/index.css)

Append vào `@layer utilities` (sau `.scrollbar-thin`, ~line 129):

```css
/* Resize handle hover indicator */
[data-panel-resize-handle-id] {
  transition: background-color 0.15s ease;
}
[data-panel-resize-handle-id]:hover,
[data-panel-resize-handle-id][data-resize-handle-active] {
  background-color: hsl(var(--primary) / 0.15);
}

/* Sidebar conversation item hover actions */
.conversation-item .action-trigger {
  opacity: 0;
  transition: opacity 0.15s ease;
}
.conversation-item:hover .action-trigger,
.conversation-item .action-trigger[data-state="open"] {
  opacity: 1;
}
```

---

## File Changes Summary

| # | Layer | File | Action | Lines Δ |
|---|-------|------|--------|---------|
| 1 | Backend | `models/mongo_logger.py` | MODIFY | +15 |
| 2 | Backend | `cache/session_store.py` | MODIFY | +25 |
| 3 | Backend | `api/routes/session.py` | MODIFY | +70 |
| 4 | Frontend | `services/sessionApi.ts` | MODIFY | +15 |
| 5 | Frontend | `components/sidebar/ConversationSidebar.tsx` | MODIFY (rewrite) | +160 |
| 6 | Frontend | `hooks/useResizableSidebar.ts` | NEW | ~40 |
| 7 | Frontend | `pages/Index.tsx` | MODIFY (rewrite layout) | +80 |
| 8 | Frontend | `components/chat/ChatContainer.tsx` | MODIFY | +30 |
| 9 | Frontend | `index.css` | MODIFY | +15 |

---

## Execution Order

1. Phase 1 → Backend APIs (mongo_logger → session_store → session routes)
2. Phase 2 → Frontend sessionApi
3. Phase 3 → Sidebar rewrite
4. Phase 4 → useResizableSidebar hook → Index.tsx layout
5. Phase 5 → ChatContainer empty state
6. Phase 6 → CSS polish
7. **Verify**: `npm run build` + browser test

---

## Verification Plan

```bash
# Backend quick check
cd d:\GR\src\RAG_v2
python -m pytest tests/ -k "session" -v --tb=short

# Frontend build
cd d:\GR\src\RAG_v2\frontend\chat-companion
npm run build
```

### Browser Tests
1. Sidebar resize: kéo handle → resize smooth, reload → persist size
2. Sidebar collapse: kéo quá nhỏ → collapse, Ctrl+B → toggle
3. Rename: hover item → ⋯ → Đổi tên → input → Enter → title updated
4. Delete: hover item → ⋯ → Xoá → AlertDialog → confirm → session removed
5. Mobile: sidebar = Sheet overlay, resize disabled
6. Empty state: suggestion chips → click → sends message
7. Search: type in search → filters conversations
8. Grouped list: "Hôm nay", "Hôm qua", etc.
