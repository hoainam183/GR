# Thiết kế Mobile App — RAG Student Assistant

## Mục lục
1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Gợi ý tính năng cho sinh viên](#2-gợi-ý-tính-năng-cho-sinh-viên)
3. [Thiết kế kiến trúc hệ thống](#3-thiết-kế-kiến-trúc-hệ-thống)
4. [Thiết kế API mở rộng](#4-thiết-kế-api-mở-rộng)
5. [Thiết kế Database mở rộng](#5-thiết-kế-database-mở-rộng)
6. [Thiết kế UI/UX Mobile](#6-thiết-kế-uiux-mobile)
7. [Tech Stack](#7-tech-stack)
8. [Kế hoạch triển khai](#8-kế-hoạch-triển-khai)

---

## 1. Tổng quan hệ thống

### 1.1 Hiện trạng Backend

Hệ thống RAG v2 hiện tại đã có:

| Component | Trạng thái | Ghi chú |
|-----------|-----------|---------|
| FastAPI Backend | ✅ | `/chat`, `/chat/stream` (SSE), `/health`, `/session` |
| MongoDB Session | ✅ | Session CRUD, turn logging, query logs |
| SSE Streaming | ✅ | Token-by-token streaming response |
| Query Routing | ✅ | Chitchat / RAG auto-classification (6 domains) |
| Hybrid Search | ✅ | Qdrant + Elasticsearch + RRF fusion |
| Reranking | ✅ | BGE-Reranker-v2-m3 |
| React Web Frontend | ✅ | Vite + Tailwind + shadcn/ui |

### 1.2 Những gì cần mở rộng cho Mobile

```
                    ┌─────────────────────────────────┐
                    │         Mobile App (RN)          │
                    │  ┌───────┐ ┌────────┐ ┌───────┐ │
                    │  │ Chat  │ │Profile │ │ Tools │ │
                    │  └───┬───┘ └───┬────┘ └───┬───┘ │
                    └──────┼─────────┼──────────┼─────┘
                           │         │          │
                    ┌──────▼─────────▼──────────▼─────┐
                    │     API Gateway (FastAPI)         │
                    │  ┌──────┐ ┌──────┐ ┌──────────┐ │
                    │  │/chat │ │/auth │ │/student  │  │
                    │  │/stream││/notif│ │/bookmark │  │
                    │  └──┬───┘ └──┬──┘ └────┬─────┘  │
                    └─────┼────────┼─────────┼────────┘
                          │        │         │
              ┌───────────▼──┐  ┌──▼───┐  ┌──▼──────────┐
              │ RAG Pipeline │  │Mongo │  │ Redis Cache  │
              │ (existing)   │  │  DB  │  │ (new)        │
              └──────────────┘  └──────┘  └──────────────┘
```

**Backend cần bổ sung:**
- Authentication (JWT) — quản lý user/student
- Student Profile API — thông tin khóa, ngành, chương trình
- Bookmark/Saved answers API
- Push notification service
- Cache layer (Redis)
- Rate limiting cho mobile clients

---

## 2. Gợi ý tính năng cho sinh viên

### 2.1 Tính năng Core

#### A. Chat hỏi đáp thông minh (đã có backend, cần mobile UI)
- Hỏi đáp về quy định, quy chế, CTĐT, kế hoạch, sự kiện
- Streaming response (typing effect)
- Hiển thị nguồn tham chiếu (document sources)
- Lịch sử hội thoại (multi-session)

#### B. Student Profile — Cá nhân hóa câu trả lời ⭐ (MỚI)
- Đăng ký thông tin: **Khóa** (K65-K70), **Ngành** (CNTT, ĐTVT, ...), **Chương trình** (CT, CTTT, ELITECH, ...)
- Hệ thống TỰ ĐỘNG lọc quy định đúng theo khóa/ngành
- VD: SV K68 CNTT hỏi "yêu cầu ngoại ngữ" → trả về QĐ ngoại ngữ áp dụng từ K68
- VD: SV K66 hỏi cùng câu → trả về QĐ ngoại ngữ K66 (khác nhau!)

#### C. Conversation History (đã có backend)
- Danh sách sessions trước đó
- Tìm kiếm trong lịch sử chat
- Tiếp tục hội thoại cũ

### 2.2 Tính năng Nâng cao

#### D. Bookmark & Lưu quy định quan trọng ⭐ (MỚI)
- Lưu câu trả lời hay/quan trọng
- Tạo thư mục (folder) phân loại: "Học phí", "Ngoại ngữ", "CTĐT", ...
- Chia sẻ bookmark cho bạn bè (share link)
- Quick access từ home screen

#### E. Thông báo quy định mới ⭐ (MỚI)
- Push notification khi có quy định mới liên quan đến khóa/ngành của SV
- VD: QĐ mới về ngoại ngữ K68 → notify tất cả SV K68
- Tóm tắt thay đổi so với quy định cũ (LLM-generated diff summary)
- Đăng ký theo dõi topic (subscribe)

#### F. Tra cứu nhanh (Quick Lookup) ⭐ (MỚI)
- **Tra cứu CTĐT:** Nhập mã ngành → hiển thị cây CTĐT (tín chỉ, môn bắt buộc/tự chọn)
- **Tra cứu quy định theo chủ đề:** Danh mục quy định phân theo category (tree view)
- **Tra cứu lịch:** Lịch thi, lịch đăng ký, deadline quan trọng
- **So sánh quy định giữa các khóa:** K66 vs K68 khác gì? (LLM-generated comparison)

#### G. FAQ & Suggested Questions ⭐ (MỚI)
- Gợi ý câu hỏi phổ biến theo khóa/ngành (personalized)
- FAQ tĩnh cho các câu hỏi thường gặp nhất (cache sẵn)
- "Mọi người cũng hỏi" — popular questions gần đây

#### H. Offline Mode (Partial) ⭐ (MỚI)
- Cache FAQ responses locally
- Lưu bookmarks offline
- Hiển thị thông báo "cần kết nối để hỏi câu hỏi mới"

#### I. Feedback & Rating ⭐ (MỚI)
- 👍/👎 cho mỗi câu trả lời
- Flag câu trả lời sai
- Comment chi tiết (optional)
- Data feedback → cải thiện hệ thống (RLHF-lite)

### 2.3 Bảng tổng hợp tính năng & ưu tiên

| # | Tính năng | Ưu tiên | Effort | Phụ thuộc Backend |
|---|-----------|---------|--------|-------------------|
| A | Chat hỏi đáp + streaming | 🔴 P0 | 5d | Có sẵn |
| B | Student Profile | 🔴 P0 | 3d app + 2d API | Cần API mới |
| C | History (multi-session) | 🔴 P0 | 2d | Có sẵn |
| D | Bookmark & Lưu | 🟡 P1 | 3d app + 1d API | Cần API mới |
| E | Thông báo quy định mới | 🟡 P1 | 3d app + 3d API | Cần service mới |
| F | Tra cứu nhanh | 🟡 P1 | 4d app + 2d API | Cần API mới |
| G | FAQ & Suggested | 🟢 P2 | 2d app + 1d API | Cần API mới |
| H | Offline mode | 🟢 P2 | 2d | Không |
| I | Feedback | 🟢 P2 | 1d app + 1d API | Cần API mới |

---

## 3. Thiết kế kiến trúc hệ thống

### 3.1 Kiến trúc tổng thể

```
┌──────────────────────────────────────────────────────────────┐
│                        MOBILE APP                            │
│                    (React Native / Expo)                      │
│                                                              │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌──────────────┐  │
│  │  Chat   │  │ Profile  │  │ Lookup  │  │  Bookmarks   │  │
│  │ Screen  │  │ Screen   │  │ Screen  │  │   Screen     │  │
│  └────┬────┘  └────┬─────┘  └────┬────┘  └──────┬───────┘  │
│       │            │             │               │           │
│  ┌────▼────────────▼─────────────▼───────────────▼────────┐ │
│  │              API Service Layer (axios)                   │ │
│  │  ┌──────┐ ┌────────┐ ┌──────────┐ ┌──────────────────┐ │ │
│  │  │Auth  │ │Chat API│ │Student   │ │Bookmark/Feedback │ │ │
│  │  │Service│ │Service │ │Service   │ │Service           │ │ │
│  │  └──────┘ └────────┘ └──────────┘ └──────────────────┘ │ │
│  └─────────────────────────┬──────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────▼──────────────────────────────┐ │
│  │           Local Storage (AsyncStorage / MMKV)           │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐ │ │
│  │  │ JWT Token│  │ Cached FAQs  │  │ Offline Bookmarks│ │ │
│  │  └──────────┘  └──────────────┘  └──────────────────┘ │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                           │ HTTPS
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                          │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  API Gateway Layer                       │ │
│  │  ┌──────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐ │ │
│  │  │Auth      │  │ Rate   │  │ Request  │  │  CORS    │ │ │
│  │  │Middleware │  │Limiter │  │Validator │  │          │ │ │
│  │  └──────────┘  └────────┘  └──────────┘  └──────────┘ │ │
│  └─────────────────────────┬───────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────▼───────────────────────────────┐ │
│  │                    Route Groups                          │ │
│  │                                                         │ │
│  │  /auth/*          /chat/*        /student/*             │ │
│  │  ├── POST /login  ├── POST /     ├── GET  /profile      │ │
│  │  ├── POST /register├── POST /stream├── PUT  /profile    │ │
│  │  └── POST /refresh└── GET /suggest└── GET  /regulations │ │
│  │                                                         │ │
│  │  /bookmark/*      /feedback/*    /notification/*        │ │
│  │  ├── POST /       ├── POST /     ├── GET  /             │ │
│  │  ├── GET  /       └── GET /stats ├── POST /subscribe    │ │
│  │  ├── DELETE /:id                 └── PUT  /read         │ │
│  │  └── GET /folders                                       │ │
│  │                                                         │ │
│  │  /session/*       /lookup/*                             │ │
│  │  ├── POST /       ├── GET /ctdt/:major                  │ │
│  │  ├── GET  /:id    ├── GET /regulations/:category        │ │
│  │  └── GET  /list   └── GET /calendar                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────▼───────────────────────────────┐ │
│  │                  Service Layer                           │ │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │ │
│  │  │RAGPipeline │  │StudentCtx  │  │NotificationSvc   │  │ │
│  │  │(existing)  │  │Builder     │  │(new)             │  │ │
│  │  └────────────┘  └────────────┘  └──────────────────┘  │ │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │ │
│  │  │CacheManager│  │BookmarkSvc │  │FeedbackCollector │  │ │
│  │  │(Redis)     │  │(new)       │  │(new)             │  │ │
│  │  └────────────┘  └────────────┘  └──────────────────┘  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                 │
│  ┌─────────────────────────▼───────────────────────────────┐ │
│  │                  Data Layer                              │ │
│  │  ┌────────┐  ┌───────────┐  ┌──────┐  ┌─────────────┐ │ │
│  │  │MongoDB │  │Qdrant     │  │Redis │  │Elasticsearch│ │ │
│  │  │sessions│  │embeddings │  │cache │  │BM25 index   │ │ │
│  │  │users   │  │           │  │      │  │             │ │ │
│  │  │bookmarks│ │           │  │      │  │             │ │ │
│  │  │feedback│  │           │  │      │  │             │ │ │
│  │  └────────┘  └───────────┘  └──────┘  └─────────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Authentication Flow

```
Mobile App                    Backend                     MongoDB
    │                            │                           │
    │  POST /auth/register       │                           │
    │  {mssv, password, cohort,  │                           │
    │   major, program}          │                           │
    │ ──────────────────────────>│                           │
    │                            │  Insert user doc          │
    │                            │ ─────────────────────────>│
    │                            │                           │
    │  {access_token, refresh}   │                           │
    │ <──────────────────────────│                           │
    │                            │                           │
    │  POST /chat/stream         │                           │
    │  Authorization: Bearer xxx │                           │
    │  {question, session_id}    │                           │
    │ ──────────────────────────>│                           │
    │                            │  Decode JWT → user_id     │
    │                            │  Load student profile     │
    │                            │  Build metadata filters   │
    │                            │  RAG pipeline + filters   │
    │                            │                           │
    │  SSE: streaming response   │                           │
    │ <──────────────────────────│                           │
```

**Lưu ý bảo mật:**
- JWT access token (15 phút) + refresh token (7 ngày)
- Password hash bằng bcrypt
- Rate limiting: 30 requests/phút cho chat, 5 requests/phút cho auth
- HTTPS bắt buộc
- Input sanitization (đã có qua Pydantic)

### 3.3 Chat Flow có Student Context (cải tiến)

```
User hỏi: "Yêu cầu ngoại ngữ tốt nghiệp là gì?"
               │
               ▼
┌─────────────────────────┐
│ 1. Auth Middleware       │ → Decode JWT → user_id
│    Load Student Profile  │ → {cohort: "K68", major: "CNTT", program: "standard"}
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 2. Query Router          │ → intent: "quydinh"
│    (classifier / LLM)    │   domain: "ngoại ngữ"
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 3. Context Filter Builder│ → Qdrant filter:
│    (MỚI)                 │   {applicable_cohort: contains "K68",
│                          │    OR applicable_cohort: "all"}
│                          │   ES filter:
│                          │   {applicable_cohort: ["K68", "all"]}
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 4. Reflection            │ → "Yêu cầu ngoại ngữ tốt nghiệp cho
│    (existing)            │    sinh viên K68 ngành CNTT là gì?"
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 5. Embed + Hybrid Search │ → Search WITH filters
│    + Rerank (existing)   │   → Chỉ trả về QĐ áp dụng cho K68
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 6. Validity Filter (MỚI)│ → Loại bỏ QĐ đã bị thay thế
│                          │   VD: QĐ 2023 bị thay bởi QĐ 2025
└────────────┬────────────┘
             ▼
┌─────────────────────────┐
│ 7. Generate + Self-eval  │ → Trả lời chính xác cho K68
│    (existing)            │
└────────────┬────────────┘
             ▼
        Response + Sources
```

---

## 4. Thiết kế API mở rộng

### 4.1 API Endpoints mới

#### Auth Routes (`/auth/*`)

```
POST /auth/register
  Request:  {mssv: str, password: str, full_name: str,
             cohort: str, major: str, program: str}
  Response: {access_token: str, refresh_token: str, user_id: str}

POST /auth/login
  Request:  {mssv: str, password: str}
  Response: {access_token: str, refresh_token: str, user_id: str}

POST /auth/refresh
  Request:  {refresh_token: str}
  Response: {access_token: str}

POST /auth/logout
  Request:  {} (Authorization header)
  Response: {status: "ok"}
```

#### Student Routes (`/student/*`) [Yêu cầu auth]

```
GET /student/profile
  Response: {user_id, mssv, full_name, cohort, major, program,
             created_at, preferences: {...}}

PUT /student/profile
  Request:  {full_name?, cohort?, major?, program?, preferences?}
  Response: {updated profile}

GET /student/regulations
  → Trả về danh sách quy định áp dụng cho SV này (filtered by cohort/major)
  Response: {regulations: [{title, effective_date, category, summary}]}
```

#### Chat Routes (mở rộng) [Yêu cầu auth]

```
POST /chat
  Request:  {question: str, top_k: int, session_id?: str}
  → Backend TỰ ĐỘNG inject student_context từ JWT/profile
  Response: {question, answer, retrieved_documents, session_id, intent}

POST /chat/stream
  → Tương tự, SSE streaming

GET /chat/suggest
  → Gợi ý câu hỏi phổ biến cho SV này (dựa trên cohort/major)
  Response: {suggestions: [{question, category, popularity}]}
```

#### Bookmark Routes (`/bookmark/*`) [Yêu cầu auth]

```
POST /bookmark
  Request:  {session_id: str, turn_id: int, folder?: str, note?: str}
  Response: {bookmark_id, created_at}

GET /bookmark
  Query:    ?folder=ngoai_ngu&page=1&limit=20
  Response: {bookmarks: [{id, question, answer_preview, folder, created_at}],
             total, page}

DELETE /bookmark/{bookmark_id}
  Response: {status: "deleted"}

GET /bookmark/folders
  Response: {folders: [{name, count}]}

POST /bookmark/folders
  Request:  {name: str}
  Response: {folder created}
```

#### Feedback Routes (`/feedback/*`) [Yêu cầu auth]

```
POST /feedback
  Request:  {session_id: str, turn_id: int, rating: "up"|"down",
             comment?: str, category?: "wrong"|"incomplete"|"outdated"}
  Response: {feedback_id}

GET /feedback/stats  (admin only)
  Response: {total, positive_rate, top_negative_categories}
```

#### Session Routes (mở rộng) [Yêu cầu auth]

```
GET /session/list
  Query:    ?page=1&limit=20
  Response: {sessions: [{session_id, title, last_message, updated_at,
             turn_count}], total}

DELETE /session/{session_id}
  Response: {status: "deleted"}
```

#### Notification Routes (`/notification/*`) [Yêu cầu auth]

```
GET /notification
  Query:    ?unread_only=true&page=1
  Response: {notifications: [{id, title, body, type, read, created_at}]}

PUT /notification/{id}/read
  Response: {status: "read"}

POST /notification/subscribe
  Request:  {topics: ["quydinh_K68", "ctdt_CNTT"], fcm_token: str}
  Response: {subscribed_topics}
```

#### Lookup Routes (`/lookup/*`) [Public hoặc auth]

```
GET /lookup/ctdt/{major_code}
  Query:    ?cohort=K68
  Response: {program_name, total_credits, semesters: [{courses}]}

GET /lookup/regulations
  Query:    ?category=ngoai_ngu&cohort=K68
  Response: {regulations: [{title, summary, effective_date, applies_to}]}

GET /lookup/calendar
  Query:    ?semester=20252
  Response: {events: [{title, date, type, description}]}

GET /lookup/compare
  Query:    ?topic=ngoai_ngu&cohort1=K66&cohort2=K68
  Response: {comparison: {topic, differences: [{aspect, k66_value, k68_value}]}}
```

### 4.2 Schema mở rộng (Pydantic)

```python
# api/schemas.py — additions

class StudentInfo(BaseModel):
    """Student profile embedded in request context."""
    cohort: str = Field(..., pattern=r"^K\d{2}$")  # K65, K66, ..., K70
    major: str
    program: str = "standard"  # standard | cttt | elitech | ...

class ChatRequest(BaseModel):  # UPDATED
    question: str = Field(..., min_length=1, max_length=4096)
    top_k: int = Field(default=5, ge=1, le=50)
    session_id: Optional[str] = None
    # history field REMOVED — auto-loaded from session
    # student_info auto-injected from JWT, not sent by client

class BookmarkCreate(BaseModel):
    session_id: str
    turn_id: int
    folder: Optional[str] = None
    note: Optional[str] = None

class FeedbackCreate(BaseModel):
    session_id: str
    turn_id: int
    rating: Literal["up", "down"]
    comment: Optional[str] = Field(None, max_length=1000)
    category: Optional[Literal["wrong", "incomplete", "outdated"]] = None

class NotificationSubscribe(BaseModel):
    topics: List[str]
    fcm_token: str
```

---

## 5. Thiết kế Database mở rộng

### 5.1 MongoDB Collections

```
rag_chatbot (database)
├── users                    # MỚI — user accounts
│   {
│     _id, mssv, password_hash, full_name,
│     cohort: "K68", major: "CNTT", program: "standard",
│     created_at, updated_at,
│     preferences: {language: "vi", notifications_enabled: true},
│     fcm_tokens: ["token1", "token2"]
│   }
│
├── sessions                 # EXISTING — mở rộng thêm user_id
│   {
│     session_id, user_id,   # ← thêm user_id
│     title,                 # ← thêm auto-generated title
│     created_at, updated_at, turn_count,
│     turns: [{turn_id, question, answer, intent, latency_ms, timestamp}]
│   }
│
├── query_logs               # EXISTING — giữ nguyên
│
├── bookmarks                # MỚI
│   {
│     _id, user_id, session_id, turn_id,
│     question, answer_snapshot, sources_snapshot,
│     folder: "ngoai_ngu",
│     note: "Quan trọng cho kỳ tới",
│     created_at
│   }
│   Indexes: (user_id, folder), (user_id, created_at DESC)
│
├── feedback                 # MỚI
│   {
│     _id, user_id, session_id, turn_id,
│     rating: "up"|"down",
│     comment, category,
│     question, answer_snapshot,
│     created_at
│   }
│   Indexes: (created_at DESC), (rating), (category)
│
├── notifications            # MỚI
│   {
│     _id, user_id, title, body,
│     type: "new_regulation"|"update"|"reminder",
│     related_doc_id,
│     read: false,
│     created_at
│   }
│   Indexes: (user_id, read, created_at DESC)
│
├── notification_subscriptions  # MỚI
│   {
│     _id, user_id, topics: ["quydinh_K68", "ctdt_CNTT"],
│     fcm_token, updated_at
│   }
│
├── document_registry        # MỚI (for validity tracking)
│   {
│     _id, doc_id: "QCDT_2025_5445",
│     title, category, effective_date,
│     replaces: ["QCDT_2023_4600"],
│     applicable_cohorts: ["K68", "K69", "K70"],
│     applicable_majors: ["all"],
│     status: "active"|"superseded",
│     superseded_by: null
│   }
│
└── faq_cache                # MỚI
    {
      _id, question, answer, sources,
      cohort_scope: "K68"|"all",
      major_scope: "CNTT"|"all",
      category, hit_count, last_accessed,
      created_at, expires_at
    }
    Indexes: (cohort_scope, major_scope, category), (hit_count DESC)
```

### 5.2 Redis Cache Structure

```
Cache Keys:

# Embedding cache (TTL: 24h)
emb:bge:{hash(query)}  →  [float array]
emb:e5:{hash(query)}   →  [float array]

# Retrieval cache (TTL: 1h)
search:{hash(query+filters)}  →  [retrieved docs JSON]

# Response cache — FAQ (TTL: 6h)
faq:{hash(question)}:{cohort}:{major}  →  {answer, sources}

# Rate limiting (TTL: 60s)
rate:{user_id}:chat  →  counter
rate:{ip}:auth       →  counter

# Session cache (TTL: 30m)
session:{session_id}:history  →  [last 6 turns]

# User profile cache (TTL: 1h)
user:{user_id}:profile  →  {cohort, major, program}
```

---

## 6. Thiết kế UI/UX Mobile

### 6.1 Navigation Structure

```
Bottom Tab Navigator
├── 🏠 Home (Chat)
│   ├── New Chat Screen
│   ├── Chat Detail Screen (streaming messages)
│   └── Source Viewer (bottom sheet)
│
├── 📚 Tra cứu (Lookup)
│   ├── Categories Grid
│   ├── CTĐT Viewer
│   ├── Regulation Browser
│   └── Calendar View
│
├── 🔖 Đã lưu (Bookmarks)
│   ├── Folders List
│   └── Bookmark Detail
│
├── 🔔 Thông báo (Notifications)
│   └── Notification List
│
└── 👤 Tài khoản (Profile)
    ├── Student Info
    ├── Edit Profile
    ├── Settings
    └── Session History
```

### 6.2 Wireframe các màn hình chính

#### Home / Chat Screen
```
┌─────────────────────────┐
│ ← HUST Student Assistant│
│    Session: "Hỏi về..." │
├─────────────────────────┤
│                         │
│  ┌───────────────────┐  │
│  │ 👤 Yêu cầu ngoại │  │
│  │ ngữ tốt nghiệp?  │  │
│  └───────────────────┘  │
│                         │
│  ┌───────────────────┐  │
│  │ 🤖 Theo QĐ áp    │  │
│  │ dụng cho K68:     │  │
│  │ ...               │  │
│  │ ───────────────── │  │
│  │ 📄 2 nguồn tham   │  │
│  │    chiếu  ▼       │  │
│  │ 👍 👎 🔖         │  │
│  └───────────────────┘  │
│                         │
│ ┌─────────────────────┐ │
│ │ Gợi ý:             │ │
│ │ • Điểm rèn luyện?  │ │
│ │ • Học bổng K68?     │ │
│ └─────────────────────┘ │
├─────────────────────────┤
│ ┌─────────────────┐ ┌─┐│
│ │ Nhập câu hỏi... │ │▶││
│ └─────────────────┘ └─┘│
└─────────────────────────┘
  🏠    📚    🔖    🔔  👤
```

#### Profile Screen
```
┌─────────────────────────┐
│      Thông tin SV       │
├─────────────────────────┤
│                         │
│   ┌─────────────────┐   │
│   │     👤 Avatar    │   │
│   │  Nguyễn Văn A   │   │
│   │  MSSV: 20210001 │   │
│   └─────────────────┘   │
│                         │
│  ┌───────────────────┐  │
│  │ Khóa:     K68    ▼│  │
│  │ Ngành:    CNTT   ▼│  │
│  │ Chương trình: CT ▼│  │
│  └───────────────────┘  │
│                         │
│  ⓘ Thông tin này giúp   │
│  hệ thống trả lời      │
│  chính xác hơn cho bạn  │
│                         │
│  ┌───────────────────┐  │
│  │   Cập nhật ✓      │  │
│  └───────────────────┘  │
│                         │
│  ─────────────────────  │
│  📋 Lịch sử hội thoại  │
│  ⚙️  Cài đặt            │
│  🔔 Quản lý thông báo  │
│  ℹ️  Về ứng dụng        │
│  🚪 Đăng xuất           │
└─────────────────────────┘
  🏠    📚    🔖    🔔  👤
```

#### Lookup Screen
```
┌─────────────────────────┐
│       Tra cứu           │
├─────────────────────────┤
│ ┌─────────────────────┐ │
│ │ 🔍 Tìm kiếm...     │ │
│ └─────────────────────┘ │
│                         │
│ ┌──────────┐┌──────────┐│
│ │ 📋 CTĐT  ││ 📜 Quy   ││
│ │          ││   định   ││
│ └──────────┘└──────────┘│
│ ┌──────────┐┌──────────┐│
│ │ 📅 Lịch  ││ 🔄 So    ││
│ │          ││   sánh   ││
│ └──────────┘└──────────┘│
│                         │
│ ── Quy định theo khóa ─│
│                         │
│ K68                     │
│ ├── Ngoại ngữ          │
│ ├── Quy chế đào tạo    │
│ ├── Điểm rèn luyện     │
│ └── Học bổng            │
│                         │
│ K67                     │
│ ├── Ngoại ngữ          │
│ └── ...                 │
└─────────────────────────┘
  🏠    📚    🔖    🔔  👤
```

### 6.3 Component Tree (React Native)

```
App
├── NavigationContainer
│   └── BottomTabNavigator
│       ├── HomeStack
│       │   ├── SessionListScreen
│       │   ├── ChatScreen
│       │   │   ├── MessageList
│       │   │   │   ├── UserMessage
│       │   │   │   ├── AssistantMessage
│       │   │   │   │   ├── StreamingText
│       │   │   │   │   ├── SourcesCollapsible
│       │   │   │   │   └── ActionBar (👍👎🔖)
│       │   │   │   └── TypingIndicator
│       │   │   ├── SuggestedQuestions
│       │   │   └── ChatInput
│       │   └── SourceDetailSheet
│       │
│       ├── LookupStack
│       │   ├── LookupHomeScreen
│       │   ├── CTDTViewerScreen
│       │   ├── RegulationBrowserScreen
│       │   ├── CalendarScreen
│       │   └── ComparisonScreen
│       │
│       ├── BookmarkStack
│       │   ├── BookmarkListScreen
│       │   └── BookmarkDetailScreen
│       │
│       ├── NotificationStack
│       │   └── NotificationListScreen
│       │
│       └── ProfileStack
│           ├── ProfileScreen
│           ├── EditProfileScreen
│           ├── SettingsScreen
│           └── SessionHistoryScreen
│
├── AuthStack (khi chưa đăng nhập)
│   ├── LoginScreen
│   ├── RegisterScreen
│   └── OnboardingScreen (chọn khóa/ngành lần đầu)
│
└── Providers
    ├── AuthProvider (JWT context)
    ├── QueryClientProvider (React Query)
    └── ThemeProvider
```

---

## 7. Tech Stack

### 7.1 Mobile App

| Layer | Technology | Lý do chọn |
|-------|-----------|------------|
| **Framework** | React Native + Expo | Cross-platform (iOS + Android), cùng hệ sinh thái React với web frontend hiện tại |
| **Navigation** | React Navigation v6 | Standard cho RN, bottom tabs + stack navigator |
| **State Management** | Zustand | Lightweight, đơn giản hơn Redux cho app vừa |
| **Server State** | TanStack React Query | Đã dùng trên web frontend, caching + refetch tự động |
| **HTTP Client** | axios | Đã dùng trên web frontend |
| **SSE Streaming** | react-native-sse hoặc EventSource polyfill | Tương thích với SSE endpoint hiện có |
| **Local Storage** | MMKV (react-native-mmkv) | Nhanh hơn AsyncStorage 30x, cho cache + JWT |
| **UI Components** | React Native Paper hoặc NativeWind (Tailwind) | NativeWind nếu muốn reuse Tailwind classes từ web |
| **Push Notification** | Firebase Cloud Messaging | Standard, free |
| **Auth Token** | JWT + Secure Store (expo-secure-store) | Lưu token an toàn |
| **Markdown Render** | react-native-markdown-display | Cho hiển thị answer formatting |
| **Animation** | react-native-reanimated | Typing indicator, smooth transitions |

### 7.2 Backend bổ sung

| Component | Technology | Ghi chú |
|-----------|-----------|---------|
| **Auth** | python-jose (JWT) + passlib (bcrypt) | Lightweight, không cần OAuth server |
| **Cache** | Redis + redis-py (async) | Embedding cache, rate limiting, session cache |
| **Push Notification** | firebase-admin SDK | Gửi FCM notifications |
| **Rate Limiting** | slowapi hoặc custom Redis-based | Bảo vệ API |
| **Background Tasks** | FastAPI BackgroundTasks hoặc Celery | Notification dispatch, cache warming |

### 7.3 Tổng quan dependency flow

```
Mobile App (React Native / Expo)
    │
    │  HTTPS + JWT
    ▼
FastAPI Backend
    ├── Auth: python-jose + passlib
    ├── Cache: Redis (aioredis)
    ├── Notification: firebase-admin
    ├── RAG: existing pipeline (unchanged)
    └── DB: MongoDB (existing pymongo)
```

---

## 8. Kế hoạch triển khai

### 8.1 Tổng quan Phases

```
Phase 1 (Tuần 1-2):  Backend Auth + Student Profile + Cache
Phase 2 (Tuần 2-3):  Mobile App Scaffold + Auth + Chat Core
Phase 3 (Tuần 3-4):  Streaming Chat + History + Student Context Integration
Phase 4 (Tuần 4-5):  Bookmark + Feedback + Lookup API
Phase 5 (Tuần 5-6):  Notification + Polish + Testing
Phase 6 (Tuần 6-7):  Integration Testing + Deployment
```

### 8.2 Chi tiết Tasks

---

#### Phase 1: Backend mở rộng (Tuần 1-2)

**Mục tiêu:** Backend sẵn sàng cho mobile client

| # | Task | File(s) | Effort | Phụ thuộc |
|---|------|---------|--------|-----------|
| 1.1 | Cài đặt dependencies: `python-jose`, `passlib[bcrypt]`, `redis`, `slowapi` | `requirements.txt` | 0.5d | — |
| 1.2 | Tạo User model + Auth service (register/login/JWT) | `api/auth.py` (mới), `api/routes/auth.py` (mới) | 2d | — |
| 1.3 | Auth middleware (JWT decode, inject user vào request) | `api/middleware/auth.py` (mới) | 1d | 1.2 |
| 1.4 | Student Profile API (GET/PUT /student/profile) | `api/routes/student.py` (mới) | 1d | 1.2, 1.3 |
| 1.5 | Redis cache setup + Embedding cache wrapper | `config/settings.py` (update), `cache/redis_client.py` (mới), `embedding/cache.py` (mới) | 1.5d | 1.1 |
| 1.6 | Rate limiting middleware | `api/middleware/rate_limit.py` (mới) | 0.5d | 1.5 |
| 1.7 | Mở rộng ChatRequest: bỏ `history` field (auto-load), inject student context | `api/schemas.py`, `api/routes/chat.py` | 1d | 1.3, 1.4 |
| 1.8 | Student context → metadata filter builder | `query/context_extractor.py` (mới), `retrieval/filter_builder.py` (mới) | 2d | 1.4 |
| 1.9 | Tích hợp filter vào pipeline flow | `pipeline/flows.py`, `pipeline/rag_pipeline.py` | 1d | 1.8 |
| 1.10 | Session list API (GET /session/list cho mobile) | `api/routes/session.py` (update) | 0.5d | 1.3 |

**Deliverable:** Backend API chạy được với auth, student profile, filtered search

---

#### Phase 2: Mobile App Scaffold (Tuần 2-3)

**Mục tiêu:** App chạy được, đăng nhập + chat cơ bản

| # | Task | File(s) | Effort | Phụ thuộc |
|---|------|---------|--------|-----------|
| 2.1 | Khởi tạo Expo project + cấu hình (TypeScript, ESLint, Prettier) | `mobile/` (mới) | 0.5d | — |
| 2.2 | Setup navigation: BottomTab + Stack navigators | `mobile/src/navigation/` | 1d | 2.1 |
| 2.3 | UI Kit setup: NativeWind (Tailwind) hoặc RN Paper | `mobile/tailwind.config.ts` hoặc `mobile/src/theme/` | 0.5d | 2.1 |
| 2.4 | Auth screens: Login + Register + Onboarding (chọn khóa/ngành) | `mobile/src/screens/auth/` | 2d | 2.2 |
| 2.5 | Auth service: JWT storage (expo-secure-store), auto-refresh, axios interceptor | `mobile/src/services/auth.ts`, `mobile/src/hooks/useAuth.ts` | 1.5d | 2.4, Phase 1 |
| 2.6 | Chat screen: MessageList + ChatInput (static, no streaming yet) | `mobile/src/screens/chat/ChatScreen.tsx` | 2d | 2.2 |
| 2.7 | Chat API service: sendMessage, non-streaming first | `mobile/src/services/chatApi.ts` | 0.5d | 2.5 |
| 2.8 | Profile screen: hiển thị + edit student info | `mobile/src/screens/profile/ProfileScreen.tsx` | 1d | 2.5 |

**Deliverable:** App đăng nhập được, gửi/nhận chat cơ bản, xem/sửa profile

---

#### Phase 3: Chat nâng cao (Tuần 3-4)

**Mục tiêu:** Streaming, history, sources, gợi ý câu hỏi

| # | Task | File(s) | Effort | Phụ thuộc |
|---|------|---------|--------|-----------|
| 3.1 | SSE streaming integration cho React Native | `mobile/src/services/sseClient.ts`, `mobile/src/hooks/useStreamChat.ts` | 2d | 2.7 |
| 3.2 | StreamingText component (typing effect) | `mobile/src/components/chat/StreamingText.tsx` | 1d | 3.1 |
| 3.3 | Session list screen (danh sách hội thoại cũ) | `mobile/src/screens/chat/SessionListScreen.tsx` | 1d | 2.5 |
| 3.4 | Source viewer (bottom sheet hiển thị tài liệu gốc) | `mobile/src/components/chat/SourceSheet.tsx` | 1d | 2.6 |
| 3.5 | Suggested questions component (personalized by cohort/major) | `mobile/src/components/chat/SuggestedQuestions.tsx` | 1d | Phase 1.7 |
| 3.6 | Backend: GET /chat/suggest API | `api/routes/chat.py` (update) | 1d | Phase 1.4 |
| 3.7 | Markdown rendering cho answer | `mobile/src/components/chat/MarkdownMessage.tsx` | 0.5d | 2.6 |
| 3.8 | Action bar (👍👎🔖) trên mỗi message | `mobile/src/components/chat/MessageActions.tsx` | 0.5d | 2.6 |

**Deliverable:** Chat streaming hoàn chỉnh, xem sources, gợi ý câu hỏi

---

#### Phase 4: Bookmark + Feedback + Lookup (Tuần 4-5)

**Mục tiêu:** Tính năng phụ trợ cho trải nghiệm sinh viên

| # | Task | File(s) | Effort | Phụ thuộc |
|---|------|---------|--------|-----------|
| 4.1 | Backend: Bookmark CRUD API | `api/routes/bookmark.py` (mới) | 1d | Phase 1.3 |
| 4.2 | Backend: Feedback API | `api/routes/feedback.py` (mới) | 0.5d | Phase 1.3 |
| 4.3 | Backend: Lookup APIs (CTDT, regulations, calendar, compare) | `api/routes/lookup.py` (mới) | 2d | Phase 1.4 |
| 4.4 | Mobile: Bookmark screen (list + folders + detail) | `mobile/src/screens/bookmark/` | 2d | 4.1 |
| 4.5 | Mobile: Feedback flow (from message action bar) | `mobile/src/services/feedbackApi.ts` | 0.5d | 4.2, 3.8 |
| 4.6 | Mobile: Lookup home screen (categories grid) | `mobile/src/screens/lookup/LookupHomeScreen.tsx` | 1d | 4.3 |
| 4.7 | Mobile: CTDT viewer screen | `mobile/src/screens/lookup/CTDTViewerScreen.tsx` | 1.5d | 4.3 |
| 4.8 | Mobile: Regulation browser (tree view by category/cohort) | `mobile/src/screens/lookup/RegulationBrowserScreen.tsx` | 1.5d | 4.3 |
| 4.9 | Mobile: Comparison screen (K66 vs K68 diff) | `mobile/src/screens/lookup/ComparisonScreen.tsx` | 1d | 4.3 |

**Deliverable:** Bookmark, feedback, tra cứu CTĐT, quy định, so sánh khóa

---

#### Phase 5: Notification + Polish (Tuần 5-6)

**Mục tiêu:** Push notification, offline cache, UX polish

| # | Task | File(s) | Effort | Phụ thuộc |
|---|------|---------|--------|-----------|
| 5.1 | Backend: Firebase Admin SDK setup + notification service | `services/notification.py` (mới), `api/routes/notification.py` (mới) | 2d | Phase 1.2 |
| 5.2 | Backend: Background task phát hiện document mới → tạo notification | `services/doc_watcher.py` (mới) | 1.5d | 5.1 |
| 5.3 | Mobile: FCM setup + push handling | `mobile/src/services/pushNotification.ts` | 1.5d | 5.1 |
| 5.4 | Mobile: Notification screen (list + mark read) | `mobile/src/screens/notification/NotificationListScreen.tsx` | 1d | 5.3 |
| 5.5 | Mobile: Offline cache (FAQ cache, bookmarks sync) | `mobile/src/services/offlineCache.ts` | 1d | 4.4 |
| 5.6 | Mobile: Onboarding flow (first-time user: chọn khóa, ngành) | `mobile/src/screens/auth/OnboardingScreen.tsx` | 1d | 2.4 |
| 5.7 | UX Polish: loading states, error handling, empty states, animations | Nhiều files | 2d | All |
| 5.8 | Dark mode support | `mobile/src/theme/` | 0.5d | 2.3 |
| 5.9 | Accessibility (screen reader, font scaling) | Nhiều files | 0.5d | All |

**Deliverable:** Notification, offline mode, UX hoàn thiện

---

#### Phase 6: Test + Deploy (Tuần 6-7)

| # | Task | Effort | Phụ thuộc |
|---|------|--------|-----------|
| 6.1 | Backend unit tests cho API mới (auth, student, bookmark, feedback) | 2d | Phase 1-5 |
| 6.2 | Mobile unit tests (components + hooks) | 1.5d | Phase 2-5 |
| 6.3 | Integration test: chat flow end-to-end (mobile → API → RAG → response) | 1d | All |
| 6.4 | Performance test: concurrent users, response time | 1d | All |
| 6.5 | Security audit: JWT flow, input validation, rate limiting | 0.5d | All |
| 6.6 | Build + deploy: Expo EAS Build (Android APK/AAB, iOS IPA) | 1d | All |
| 6.7 | Backend deploy: Docker update (add Redis, update docker-compose) | 0.5d | Phase 1 |
| 6.8 | Documentation: API docs (OpenAPI/Swagger), User guide | 1d | All |

**Deliverable:** App build sẵn sàng, API docs, test coverage

---

### 8.3 Tổng kết timeline

```
Tuần 1  ████████████████████████████  Backend Auth + Cache + Filter
Tuần 2  ████████████████████████████  Mobile Scaffold + Auth + Chat cơ bản
Tuần 3  ████████████████████████████  Streaming + History + Sources
Tuần 4  ████████████████████████████  Bookmark + Feedback + Lookup
Tuần 5  ████████████████████████████  Notification + Offline + Polish
Tuần 6  ████████████████████████████  Testing + Deploy
Tuần 7  ██████████████                Buffer + Bug fixes
```

**Tổng effort ước tính:** ~55-60 ngày công (1 dev full-stack)

### 8.4 Rủi ro & Giải pháp

| Rủi ro | Xác suất | Giải pháp |
|--------|----------|-----------|
| SSE streaming không ổn định trên RN | Trung bình | Fallback sang polling `/chat` (non-streaming) |
| FCM setup phức tạp cho iOS | Trung bình | Ưu tiên Android trước, iOS sau |
| Redis setup thêm infra | Thấp | Fallback sang in-memory LRU cache (cachetools) nếu không có Redis |
| Auth phức tạp hóa flow | Thấp | Phase đầu cho phép guest mode (hạn chế 5 câu/ngày) |
| Backend load tăng từ mobile | Trung bình | Rate limiting + response cache + queue nếu cần |

### 8.5 MVP (Minimum Viable Product) — Nếu thời gian hạn chế

Nếu chỉ có **3 tuần**, tập trung:

| Tính năng | Bao gồm |
|-----------|---------|
| ✅ Chat streaming | Core flow hoạt động |
| ✅ Student profile (cohort/major) | Tại onboarding, lưu local |
| ✅ Session history | List + continue session |
| ✅ Source viewer | Bottom sheet hiển thi sources |
| ❌ Bookmark | Bỏ qua |
| ❌ Notification | Bỏ qua |
| ❌ Lookup | Bỏ qua |
| ❌ Feedback | Bỏ qua |
| ⚠️ Auth | Simplified: chỉ cần MSSV, không password |

MVP scope: **Phase 1 (backend filter only) + Phase 2 + Phase 3**

---

## Phụ lục: Cấu trúc thư mục Mobile App

```
mobile/
├── app.json                        # Expo config
├── babel.config.js
├── package.json
├── tsconfig.json
├── tailwind.config.ts              # NativeWind
├── src/
│   ├── App.tsx                     # Root component
│   ├── navigation/
│   │   ├── RootNavigator.tsx       # Auth check → AuthStack or MainTab
│   │   ├── MainTabNavigator.tsx    # Bottom tabs
│   │   ├── HomeStack.tsx
│   │   ├── LookupStack.tsx
│   │   ├── BookmarkStack.tsx
│   │   ├── NotificationStack.tsx
│   │   └── ProfileStack.tsx
│   ├── screens/
│   │   ├── auth/
│   │   │   ├── LoginScreen.tsx
│   │   │   ├── RegisterScreen.tsx
│   │   │   └── OnboardingScreen.tsx
│   │   ├── chat/
│   │   │   ├── SessionListScreen.tsx
│   │   │   └── ChatScreen.tsx
│   │   ├── lookup/
│   │   │   ├── LookupHomeScreen.tsx
│   │   │   ├── CTDTViewerScreen.tsx
│   │   │   ├── RegulationBrowserScreen.tsx
│   │   │   ├── CalendarScreen.tsx
│   │   │   └── ComparisonScreen.tsx
│   │   ├── bookmark/
│   │   │   ├── BookmarkListScreen.tsx
│   │   │   └── BookmarkDetailScreen.tsx
│   │   ├── notification/
│   │   │   └── NotificationListScreen.tsx
│   │   └── profile/
│   │       ├── ProfileScreen.tsx
│   │       ├── EditProfileScreen.tsx
│   │       ├── SettingsScreen.tsx
│   │       └── SessionHistoryScreen.tsx
│   ├── components/
│   │   ├── chat/
│   │   │   ├── MessageList.tsx
│   │   │   ├── UserMessage.tsx
│   │   │   ├── AssistantMessage.tsx
│   │   │   ├── StreamingText.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── SourceSheet.tsx
│   │   │   ├── MessageActions.tsx
│   │   │   ├── SuggestedQuestions.tsx
│   │   │   ├── MarkdownMessage.tsx
│   │   │   └── TypingIndicator.tsx
│   │   ├── lookup/
│   │   │   ├── CategoryCard.tsx
│   │   │   ├── RegulationTree.tsx
│   │   │   └── ComparisonTable.tsx
│   │   ├── common/
│   │   │   ├── LoadingSpinner.tsx
│   │   │   ├── ErrorBoundary.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   └── Badge.tsx
│   │   └── ui/                     # Shared UI primitives
│   ├── services/
│   │   ├── api.ts                  # Axios instance + interceptors
│   │   ├── auth.ts                 # Login/register/refresh
│   │   ├── chatApi.ts              # Chat endpoints
│   │   ├── studentApi.ts           # Profile endpoints
│   │   ├── bookmarkApi.ts          # Bookmark CRUD
│   │   ├── feedbackApi.ts          # Feedback submit
│   │   ├── lookupApi.ts            # Lookup endpoints
│   │   ├── notificationApi.ts      # Notification endpoints
│   │   ├── sseClient.ts            # SSE streaming handler
│   │   └── offlineCache.ts         # MMKV offline cache
│   ├── hooks/
│   │   ├── useAuth.ts              # Auth state + actions
│   │   ├── useStreamChat.ts        # SSE streaming hook
│   │   ├── useProfile.ts           # Student profile
│   │   ├── useBookmarks.ts         # Bookmark queries
│   │   └── useNotifications.ts     # Push notification hook
│   ├── stores/
│   │   ├── authStore.ts            # Zustand: auth state
│   │   ├── chatStore.ts            # Zustand: active chat state
│   │   └── settingsStore.ts        # Zustand: app settings
│   ├── types/
│   │   ├── auth.ts
│   │   ├── chat.ts
│   │   ├── student.ts
│   │   ├── bookmark.ts
│   │   ├── notification.ts
│   │   └── lookup.ts
│   ├── utils/
│   │   ├── storage.ts              # MMKV wrapper
│   │   ├── format.ts               # Date, text formatters
│   │   └── constants.ts            # API URLs, config
│   └── theme/
│       ├── colors.ts
│       ├── typography.ts
│       └── spacing.ts
└── assets/
    ├── icon.png
    ├── splash.png
    └── fonts/
```
