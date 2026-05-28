# UI/UX Improvements — Final Implementation Plan

> [!NOTE]
> User đã approve plan. Notifications: broadcast tất cả users ✅. Config table: bổ sung `top_k` ✅.

---

## Feature 1 — Admin Charts & Graphs (Real Data, UI Polish)

Backend đã trả real data từ MongoDB. Cần bổ sung visualization và thông tin đầy đủ hơn.

### [MODIFY] [OverviewTab.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/OverviewTab.tsx)
- Gọi thêm `getUserBreakdown()` để lấy **xu hướng đăng ký** (registrations) và **phân bố role**
- Thêm biểu đồ **AreaChart đăng ký user theo ngày** (registrations trend)
- Thêm **mini donut chart phân bố role** (admin vs student)
- Thêm KPI bổ sung: **trung bình câu hỏi/phiên**, **queries/ngày**
- Cải thiện visual: trend indicators (↑↓ so với tuần trước)

### [MODIFY] [QueryAnalyticsSection.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/QueryAnalyticsSection.tsx)
- Thêm **summary KPI row** trước charts: tổng queries, avg latency, error rate, queries/ngày
- Cải thiện chart tooltips — format ngày Vietnamese `dd/MM`
- Thêm legend labels rõ ràng, consistent color scheme

### [MODIFY] [AgentAnalyticsSection.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/AgentAnalyticsSection.tsx)
- Cải thiện KPI cards visual consistency (matching OverviewTab style)
- Thêm color-coded error rate badge

### [MODIFY] [SystemTab.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/SystemTab.tsx) — Charts section
- Thêm **document total count** summary trên charts
- Thêm **Legend component** cho PieChart (collection names + counts)
- Consistent color scheme

### [MODIFY] [adminApi.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/services/adminApi.ts) — (nếu cần)
- Đã có `getUserBreakdown()` — chỉ cần import vào OverviewTab

---

## Feature 2 — Notifications khi Crawl hoàn tất

Tạo notification cho **tất cả users** khi crawl xong (không phụ thuộc push token subscription).

### [MODIFY] [admin_stats.py](file:///d:/GR/src/RAG_v2/api/routes/admin_stats.py)

**Trong `_run_crawl_with_timeout()`** (line 810-845):
- Sau khi crawl thành công (`status = "success"` hoặc `"pending_review"`), gọi `_create_crawl_notifications()`
- Tạo MongoDB connection riêng (vì chạy trong background async task, không dùng FastAPI DI)

**Thêm function `_create_crawl_notifications(crawl_result)`:**
```python
async def _create_crawl_notifications(crawl_result: dict):
    """Insert notification cho tất cả users khi crawl hoàn tất."""
    # 1. Connect MongoDB riêng
    # 2. Query tất cả user_ids từ users collection  
    # 3. Build notification: title, body (số bài mới, collection), type="crawler_update"
    # 4. metadata chứa article links nếu có
    # 5. insert_many vào notifications collection
```

### [MODIFY] [notification_admin.py](file:///d:/GR/src/RAG_v2/api/routes/notification_admin.py)
- Thêm endpoint `POST /admin/notifications/broadcast`:
  - Gửi notification đến **tất cả users** từ `users` collection (không phụ thuộc subscription)
  - Admin có thể gửi thông báo thủ công bất kỳ lúc nào

---

## Feature 3 — Login Redirect khi đã Authenticated

Khi user đã login, truy cập `/`, `/login`, `/register` → redirect đến `/chat` (hoặc `/admin` nếu admin).

### [MODIFY] [LoginPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/LoginPage.tsx)
- Thêm `useEffect` gọi `getCurrentSessionUser()` → nếu có user cached → redirect ngay
- Fallback: gọi `ensureSession()` để verify token → redirect nếu valid
- Loading state trong khi checking session
- Admin → `/admin`, User → `/chat`

### [MODIFY] [LandingPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/LandingPage.tsx)
- Thêm check session khi mount
- Đã login → redirect `/chat`

### [MODIFY] [RegisterPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/RegisterPage.tsx)
- Tương tự LoginPage — redirect nếu đã authenticated

---

## Feature 4 — Config Table cho Admin

Bảng config editable trong Admin UI, lưu runtime + persist MongoDB.

### [MODIFY] [admin_stats.py](file:///d:/GR/src/RAG_v2/api/routes/admin_stats.py)

**Thêm `GET /admin/config/env`:**
- Trả về các config có thể chỉnh sửa, nhóm theo category
- Mỗi config: key, value hiện tại, type (int/float/string), description, category

**Thêm `PUT /admin/config/env`:**  
- Nhận `Record<string, any>` — validate types, whitelist check
- Apply vào `settings` runtime
- Persist vào MongoDB `system_config` collection

**Whitelist configs được phép sửa từ UI:**

| Category | Configs |
|----------|---------|
| **Retrieval** | `top_k`, `vector_top_k`, `keyword_top_k`, `vector_weight`, `keyword_weight`, `reranker_top_k`, `reranker_score_threshold` |
| **Crawler** | `crawler_schedule_hour`, `crawler_schedule_minute`, `crawler_delay`, `crawler_retention_months` |
| **Rate Limit** | `rate_limit_rpm`, `rate_limit_rpd` |
| **Chat** | `chat_temperature`, `chat_max_tokens`, `context_doc_char_limit` |
| **Self Eval** | `self_eval_min_top_score` |
| **Tavily** | `tavily_max_results`, `tavily_web_result_count`, `tavily_search_depth` |

### [MODIFY] [SystemTab.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/SystemTab.tsx)
- Thêm section **"Cấu hình nâng cao"** sau LLM config section
- Bảng config editable nhóm theo category (accordion/collapsible)
- Mỗi config: tên hiển thị, giá trị hiện tại (input), mô tả, type validation
- Nút **"Lưu cấu hình"** gọi `PUT /admin/config/env`
- Toast success/error khi lưu

### [MODIFY] [adminApi.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/services/adminApi.ts)
- Thêm `getEnvConfig(): Promise<EnvConfigResponse>`
- Thêm `updateEnvConfig(body): Promise<EnvConfigUpdateResponse>`

### [MODIFY] [adminStats.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/types/adminStats.ts)
- Thêm `EnvConfigItem` type: `{ key, value, type, label, description, category }`
- Thêm `EnvConfigResponse` type
- Thêm `EnvConfigUpdateResponse` type

---

## File Change Summary

| File | Feature | Change Type |
|------|---------|-------------|
| [OverviewTab.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/OverviewTab.tsx) | F1 | Add charts, KPIs |
| [QueryAnalyticsSection.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/QueryAnalyticsSection.tsx) | F1 | Add KPI row, improve tooltips |
| [AgentAnalyticsSection.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/AgentAnalyticsSection.tsx) | F1 | Improve card styling |
| [SystemTab.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/SystemTab.tsx) | F1+F4 | Chart legends + config table |
| [admin_stats.py](file:///d:/GR/src/RAG_v2/api/routes/admin_stats.py) | F2+F4 | Crawl notifications + config endpoints |
| [notification_admin.py](file:///d:/GR/src/RAG_v2/api/routes/notification_admin.py) | F2 | Broadcast endpoint |
| [LoginPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/LoginPage.tsx) | F3 | Session check + redirect |
| [LandingPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/LandingPage.tsx) | F3 | Session check + redirect |
| [RegisterPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/RegisterPage.tsx) | F3 | Session check + redirect |
| [adminApi.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/services/adminApi.ts) | F4 | Config API functions |
| [adminStats.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/types/adminStats.ts) | F4 | Config types |

---

## Verification Plan

### Browser Testing
1. **Admin Dashboard** → OverviewTab hiện đầy đủ charts (registrations, role distribution)
2. **Login Redirect** → Đã login → vào `/login` hoặc `/` → auto redirect `/chat`
3. **Config Table** → SystemTab → section config nâng cao → sửa `top_k` → lưu → reload → giá trị giữ
4. **Notifications** → Admin trigger crawl → crawl xong → user thấy notification mới trong bell

### Backend Verification
- `GET /admin/config/env` trả đúng configs
- `PUT /admin/config/env` cập nhật runtime + persist MongoDB
- Crawl xong → check `notifications` collection có documents mới
