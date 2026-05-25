# Facebook-like Notification Bell UI + Crawler Notifications (Final Plan)

## Tổng quan

Thêm notification bell icon kiểu Facebook vào header, khi auto-crawler crawl xong dữ liệu mới sẽ tự động tạo notification cho **tất cả users**. Frontend dùng **polling mỗi 30s** để cập nhật realtime.

### Quyết định thiết kế đã confirm:
- ✅ **Polling** (30s interval) — không dùng SSE/WebSocket
- ✅ **Broadcast** notification cho tất cả users
- ✅ **Có link** dẫn tới bài viết trong notification
- ✅ **Auto-dismiss** dropdown khi click ra ngoài

---

## Proposed Changes

### Component 1: Backend — Crawler tạo notification sau khi index

#### [MODIFY] [auto_crawler.py](file:///d:/GR/src/RAG_v2/scripts/auto_crawler.py)

**Vị trí sửa:** Method `_notify()` (line 907-925) và `_run_single_pipeline()` (line 875)

**Thay đổi:**
1. Sửa `_notify()` thành method async, ngoài log còn tạo notification records trong MongoDB
2. Gọi từ `_run_single_pipeline()` qua asyncio event loop (vì APScheduler chạy trong sync thread)

```python
# Thêm import ở đầu file:
from datetime import timezone

# Sửa _notify() → _notify() + _create_user_notifications()
def _notify(self, summary: Dict[str, Any]) -> None:
    """Log summary + tạo notification cho users."""
    # Giữ nguyên log hiện tại (lines 908-925)
    ...
    
    # Thêm: tạo notifications trong MongoDB
    if summary.get("indexed", 0) > 0:
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            count = loop.run_until_complete(self._create_user_notifications(summary))
            loop.close()
            logger.info("Created %d user notifications.", count)
        except Exception:
            logger.warning("Failed to create user notifications", exc_info=True)

async def _create_user_notifications(self, summary: Dict[str, Any]) -> int:
    """Broadcast notification cho tất cả users khi có dữ liệu mới."""
    from models.database import (
        get_motor_client, _get_settings,
        NOTIFICATIONS_COLLECTION, USERS_COLLECTION,
    )
    _, db_name = _get_settings()
    db = get_motor_client()[db_name]

    pipeline_name = summary.get("pipeline", "unknown")
    new_articles = summary.get("new_articles", 0)
    saved_chunks = summary.get("saved_chunks", [])

    # Build body với link bài viết
    body_parts = [f"Hệ thống vừa cập nhật {new_articles} bài viết mới từ nguồn {pipeline_name}."]
    if saved_chunks:
        body_parts.append("\nBài viết mới:")
        for chunk in saved_chunks[:5]:
            title = chunk.get("title", "")
            url = chunk.get("url", "")
            if title and url:
                body_parts.append(f"• {title}\n  {url}")
            elif title:
                body_parts.append(f"• {title}")

    users_cursor = db[USERS_COLLECTION].find({}, {"_id": 1})
    user_ids = [str(u["_id"]) async for u in users_cursor]
    if not user_ids:
        return 0

    now = datetime.now(timezone.utc)
    docs = [
        {
            "user_id": uid,
            "title": "📚 Dữ liệu mới đã cập nhật",
            "body": "\n".join(body_parts),
            "type": "crawler_update",
            "read": False,
            "created_at": now,
            "related_doc_id": None,
            "metadata": {
                "pipeline": pipeline_name,
                "new_articles": new_articles,
                "indexed": summary.get("indexed", 0),
                "article_links": [
                    {"title": c.get("title", ""), "url": c.get("url", "")}
                    for c in saved_chunks[:5] if c.get("url")
                ],
            },
        }
        for uid in user_ids
    ]
    result = await db[NOTIFICATIONS_COLLECTION].insert_many(docs)
    return len(result.inserted_ids)
```

**Lưu ý quan trọng**: `summary["saved_chunks"]` đã được build sẵn bởi `_build_saved_chunk_preview()` (line 878-893) — chứa `title`, `url`, `source`, `content_preview` cho tối đa 5 chunks mới nhất. Ta tận dụng data này để tạo link trong notification.

---

### Component 2: Backend — Cập nhật notification serializer

#### [MODIFY] [notification.py](file:///d:/GR/src/RAG_v2/api/routes/notification.py)

**Vị trí sửa:** Function `_serialize_notification()` (line 24-33)

Thêm trường `metadata` vào serializer để frontend có thể hiển thị link bài viết:

```python
def _serialize_notification(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "title": doc.get("title", ""),
        "body": doc.get("body", ""),
        "type": doc.get("type", "update"),
        "related_doc_id": doc.get("related_doc_id"),
        "read": bool(doc.get("read", False)),
        "created_at": doc.get("created_at"),
        "metadata": doc.get("metadata"),           # ← THÊM
    }
```

---

### Component 3: Frontend — Cập nhật shared types

#### [MODIFY] [mobile.ts](file:///d:/GR/src/RAG_v2/packages/shared/src/types/mobile.ts)

**Vị trí sửa:** Interface `NotificationItem` (line 85-93)

Thêm trường `metadata` để chứa article links:

```typescript
export interface NotificationItem {
  id: string;
  title: string;
  body: string;
  type: string;
  related_doc_id?: string | null;
  read: boolean;
  created_at: string;
  metadata?: {                           // ← THÊM
    pipeline?: string;
    new_articles?: number;
    indexed?: number;
    article_links?: Array<{
      title: string;
      url: string;
    }>;
  } | null;
}
```

---

### Component 4: Frontend — NotificationBell Component

#### [NEW] [NotificationBell.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/NotificationBell.tsx)

Component chính — bell icon + dropdown panel Facebook-style.

**Tính năng:**
- 🔔 Bell icon (lucide `Bell`) với badge đỏ hiển thị số unread
- **Polling mỗi 30s** via React Query `refetchInterval: 30_000`
- Click bell → toggle dropdown panel
- **Auto-dismiss** khi click ra ngoài (useRef + useEffect click outside)
- Dropdown hiển thị tối đa 10 notifications gần nhất
- Mỗi item: icon theo type, title, body (truncated 2 dòng), relative time, trạng thái read/unread highlight
- Notification type `crawler_update` → hiển thị link bài viết từ `metadata.article_links`
- Click notification → mark as read
- Nút "Đánh dấu đọc tất cả" ở header dropdown
- Nút "Xem tất cả thông báo →" ở footer → navigate `/notifications`
- Bell shake animation khi unread count tăng (CSS keyframe)

**Cấu trúc UI:**
```
  🔔 ← badge đỏ "3" (nếu có unread)
   │
   ▼ click
┌─────────────────────────────────────┐
│  Thông báo                  Đọc tất │
│─────────────────────────────────────│
│  📚 Dữ liệu mới đã cập nhật       │  ← bg-primary/5 (unread)
│     Hệ thống vừa cập nhật 3 bài... │
│     • Lịch thi HK2 2025-2026       │  ← link
│     2 phút trước                    │
│─────────────────────────────────────│
│  📚 Dữ liệu mới đã cập nhật       │  ← bg-card (read)
│     Đã crawl thêm 5 bài viết...    │
│     3 giờ trước                     │
│─────────────────────────────────────│
│      Xem tất cả thông báo →        │
└─────────────────────────────────────┘
```

**Dependencies dùng:** `@tanstack/react-query`, `lucide-react` (Bell icon), `@rag/shared` (API client), `react-router-dom` (navigate). Tất cả đã có sẵn — **không cần install thêm package nào**.

**Code outline:**

```tsx
import { useState, useRef, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell } from 'lucide-react';
import {
  createApiClient, listNotifications, getUnreadCount,
  markNotificationRead, markAllNotificationsRead,
} from '@rag/shared';
import type { NotificationItem } from '@rag/shared';
import { ensureAccessToken, refreshSession, clearSession } from '@/services/authSession';

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const prevCountRef = useRef(0);

  // API client (reuse pattern from NotificationsPage)
  const client = useMemo(() => createApiClient({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
    getToken: ensureAccessToken,
    refreshAuth: async () => (await refreshSession()).access_token,
    onUnauthorized: clearSession,
    withCredentials: true,
  }), []);

  // Polling unread count mỗi 30s
  const { data: unreadData } = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: () => getUnreadCount(client),
    refetchInterval: 30_000,
  });
  const unreadCount = unreadData?.unread_count ?? 0;

  // Fetch notifications khi dropdown mở
  const { data: notifData } = useQuery({
    queryKey: ['notifications-bell'],
    queryFn: () => listNotifications(client, { limit: 10 }),
    enabled: open,
    refetchInterval: open ? 30_000 : false,
  });
  const notifications = notifData?.notifications ?? [];

  // Bell shake animation khi count tăng
  const [shaking, setShaking] = useState(false);
  useEffect(() => {
    if (unreadCount > prevCountRef.current && prevCountRef.current !== 0) {
      setShaking(true);
      setTimeout(() => setShaking(false), 600);
    }
    prevCountRef.current = unreadCount;
  }, [unreadCount]);

  // Click outside → đóng dropdown
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Mark read mutation
  const markRead = useMutation({
    mutationFn: (id: string) => markNotificationRead(client, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-bell'] });
    },
  });

  const markAllRead = useMutation({
    mutationFn: () => markAllNotificationsRead(client),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-bell'] });
    },
  });

  return (
    <div className="relative" ref={ref}>
      {/* Bell button */}
      <button onClick={() => setOpen(v => !v)} className={`... ${shaking ? 'animate-bell-shake' : ''}`}>
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && <span className="badge">{unreadCount > 99 ? '99+' : unreadCount}</span>}
      </button>

      {/* Dropdown panel */}
      {open && (
        <div className="absolute right-0 top-10 z-50 w-96 rounded-xl border shadow-lg bg-card">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <h3 className="font-semibold">Thông báo</h3>
            {unreadCount > 0 && <button onClick={() => markAllRead.mutate()}>Đọc tất cả</button>}
          </div>

          {/* Notification list */}
          <div className="max-h-[400px] overflow-y-auto">
            {notifications.map(item => (
              <NotificationRow
                key={item.id}
                item={item}
                onRead={() => { if (!item.read) markRead.mutate(item.id); }}
              />
            ))}
            {notifications.length === 0 && <p className="text-center py-8">Chưa có thông báo</p>}
          </div>

          {/* Footer */}
          <div className="border-t px-4 py-2">
            <button onClick={() => { navigate('/notifications'); setOpen(false); }}>
              Xem tất cả thông báo →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

**NotificationRow sub-component:**
```tsx
function NotificationRow({ item, onRead }: { item: NotificationItem; onRead: () => void }) {
  // Icon theo type
  const icon = item.type === 'crawler_update' ? '📚' : '📢';
  
  // Relative time
  const timeAgo = getRelativeTime(item.created_at);

  // Article links từ metadata
  const links = item.metadata?.article_links ?? [];

  return (
    <div
      onClick={onRead}
      className={`px-4 py-3 cursor-pointer hover:bg-muted/50 transition ${
        item.read ? '' : 'bg-primary/5'
      }`}
    >
      <div className="flex gap-3">
        <span className="text-lg shrink-0">{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{item.title}</p>
          <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">{item.body}</p>
          
          {/* Article links */}
          {links.length > 0 && (
            <div className="mt-1.5 space-y-0.5">
              {links.slice(0, 3).map((link, i) => (
                <a key={i} href={link.url} target="_blank" rel="noopener noreferrer"
                   className="block text-xs text-primary hover:underline truncate"
                   onClick={e => e.stopPropagation()}>
                  🔗 {link.title}
                </a>
              ))}
            </div>
          )}
          
          <span className="text-[10px] text-muted-foreground mt-1 block">{timeAgo}</span>
        </div>
        {!item.read && <span className="h-2 w-2 shrink-0 rounded-full bg-primary mt-1.5" />}
      </div>
    </div>
  );
}
```

**CSS animation** (thêm vào `index.css` hoặc `tailwind.config.ts`):
```css
@keyframes bell-shake {
  0%, 100% { transform: rotate(0deg); }
  15% { transform: rotate(14deg); }
  30% { transform: rotate(-14deg); }
  45% { transform: rotate(10deg); }
  60% { transform: rotate(-8deg); }
  75% { transform: rotate(4deg); }
}
.animate-bell-shake { animation: bell-shake 0.6s ease-in-out; }
```

---

### Component 5: Tích hợp NotificationBell vào Header

#### [MODIFY] [Index.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/Index.tsx)

**Vị trí sửa:** Header JSX (line 269-301)

Thêm `<NotificationBell />` vào giữa Bookmark button và Dark/Light toggle:

```diff
 import { Activity, Bookmark, Moon, PanelLeft, Sun } from 'lucide-react';
+import { NotificationBell } from '@/components/NotificationBell';

 // Trong header JSX (line ~280-291):
           {user && (
             <Button variant="ghost" size="icon"
               onClick={() => navigate('/bookmarks')}
               aria-label="Câu trả lời đã lưu" title="Đã lưu" className="h-8 w-8">
               <Bookmark className="h-4 w-4" />
             </Button>
           )}
+          {user && <NotificationBell />}
           <Button variant="ghost" size="icon"
             onClick={() => setIsDark((prev) => !prev)} ... >
```

---

### Component 6: Cải thiện NotificationsPage

#### [MODIFY] [NotificationsPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/NotificationsPage.tsx)

Nâng cấp UI trang full-page:
- Thêm icon theo notification type (`📚` crawler, `📢` system)
- Thêm relative time format ("2 phút trước", "3 giờ trước")
- Thêm **article links** từ `metadata.article_links` (clickable)
- Thêm nút "← Quay lại" navigate về `/chat`
- Polling `refetchInterval: 30_000` đồng bộ với bell

---

## Tóm tắt tất cả file changes

| Action | File | Mô tả |
|--------|------|-------|
| **MODIFY** | [auto_crawler.py](file:///d:/GR/src/RAG_v2/scripts/auto_crawler.py) | `_notify()` → thêm tạo notification MongoDB broadcast tất cả users, có link bài viết |
| **MODIFY** | [notification.py](file:///d:/GR/src/RAG_v2/api/routes/notification.py) | `_serialize_notification()` → thêm trường `metadata` |
| **MODIFY** | [mobile.ts](file:///d:/GR/src/RAG_v2/packages/shared/src/types/mobile.ts) | `NotificationItem` → thêm optional `metadata` field |
| **NEW** | [NotificationBell.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/NotificationBell.tsx) | Bell icon + dropdown panel Facebook-style, polling 30s |
| **MODIFY** | [Index.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/Index.tsx) | Gắn `<NotificationBell />` vào header |
| **MODIFY** | [NotificationsPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/NotificationsPage.tsx) | Thêm icon, relative time, article links |
| **MODIFY** | [tailwind.config.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/tailwind.config.ts) hoặc [index.css](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/index.css) | Thêm `bell-shake` animation keyframe |

> [!NOTE]
> **Không cần install thêm package nào.** Tất cả dependencies đã có sẵn: `@tanstack/react-query`, `lucide-react`, `@rag/shared`, `axios`, `react-router-dom`.

> [!NOTE]
> **Không cần tạo SSE endpoint hay WebSocket.** Hoàn toàn dùng polling qua React Query `refetchInterval`.

## Verification Plan

### Automated Tests
1. Chạy backend → trigger crawler thủ công qua `POST /admin/crawler/trigger`
2. Verify MongoDB `notifications` collection có records mới cho tất cả users
3. Verify `GET /notifications` trả về notifications với `metadata.article_links`
4. Verify `GET /notifications/unread-count` tăng sau khi crawler xong
5. Chạy frontend → verify bell icon hiển thị đúng trên header

### Manual Verification
1. Bell icon hiển thị badge đỏ với số unread
2. Click bell → dropdown mở, hiển thị notifications
3. Notification crawler có link bài viết clickable
4. Click notification → mark as read, badge giảm
5. Click "Đánh dấu đọc tất cả" → clear tất cả
6. Click "Xem tất cả thông báo →" → navigate `/notifications`
7. Click ra ngoài dropdown → auto-dismiss
8. Badge tự cập nhật sau 30s polling
9. Bell shake animation khi có notification mới
10. Test responsive trên mobile viewport
