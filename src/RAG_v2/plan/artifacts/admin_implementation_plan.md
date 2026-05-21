# Admin Observability Center — Final Corrected Plan

> **Approved**: 2026-05-21 · **Last updated**: 2026-05-21 22:07  
> **Decisions**: ✅ User deactivation · ✅ Phased · ✅ Manual crawler trigger  
> **Verified**: MongoDB **7.0.30** · `sessions.user_id` = `str` · `users._id` = `ObjectId`

---

## Issues Fixed From Review

### ✅ Fix 1: EP2 — ObjectId/string type mismatch

**Problem**: `sessions.user_id` stores `str("69e330bc...")` but `users._id` is `ObjectId("69e330bc...")`. A naive `$lookup` on `foreignField: "user_id"` joining with `localField: "_id"` produces 0 matches.

**Verified data**:
```
sessions.user_id = '69e330bc5081434dd6070b19'  (str)
users._id        = ObjectId('69e330bc5081434dd6070b19')  (ObjectId)
```

**Solution**: Use `$addFields` + `$toString` to convert `_id` before `$lookup`:

```python
pipeline = [
    # ... $match search filter ...
    {"$addFields": {"_id_str": {"$toString": "$_id"}}},
    {"$lookup": {
        "from": "sessions",
        "localField": "_id_str",
        "foreignField": "user_id",
        "pipeline": [{"$count": "n"}],
        "as": "_sessions",
    }},
    {"$lookup": {
        "from": "query_logs",
        "localField": "_id_str",
        "foreignField": "user_id",
        "pipeline": [{"$count": "n"}],
        "as": "_queries",
    }},
    {"$addFields": {
        "session_count": {"$ifNull": [{"$first": "$_sessions.n"}, 0]},
        "query_count": {"$ifNull": [{"$first": "$_queries.n"}, 0]},
    }},
    {"$project": {"_id_str": 0, "_sessions": 0, "_queries": 0}},
    # ... $sort, $facet ...
]
```

> [!NOTE]
> `$toString` on ObjectId is supported from MongoDB 4.0+. Our version (7.0.30) is safe.

---

### ✅ Fix 2: EP4 — p95 latency MongoDB version

**Problem**: `$percentile` requires MongoDB 7.0+.

**Verified**: MongoDB **7.0.30** → `$percentile` is safe to use.

```python
# Safe to use:
{"$group": {
    "_id": {"$dateToString": {"date": "$timestamp", "format": "%Y-%m-%d"}},
    "avg_ms": {"$avg": "$latency_ms"},
    "p95_ms": {"$percentile": {
        "input": "$latency_ms",
        "p": [0.95],
        "method": "approximate",
    }},
}}
```

**Defensive**: Add version check at startup in `admin_stats.py`:

```python
_MONGO_SUPPORTS_PERCENTILE: bool = False  # set during router init

async def _check_mongo_version(db):
    global _MONGO_SUPPORTS_PERCENTILE
    try:
        info = await db.command("buildInfo")
        major = int(info["versionArray"][0])
        _MONGO_SUPPORTS_PERCENTILE = major >= 7
    except Exception:
        _MONGO_SUPPORTS_PERCENTILE = False

# In EP4: if not _MONGO_SUPPORTS_PERCENTILE → omit p95_ms field (return null)
```

---

### ✅ Fix 3: EP9 — Background thread leak

**Problem**: `asyncio.to_thread()` has no timeout. If `run()` hangs on network I/O, `_crawl_running` stays True forever.

**Solution**: Timeout wrapper + `try/finally` guarantee:

```python
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

_crawl_lock = threading.Lock()
_crawl_running = False
_last_manual_crawl: dict | None = None
_CRAWL_TIMEOUT_SECONDS = 600  # 10 minutes max

_crawl_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="crawl")

async def _run_crawl_with_timeout(crawl_pipeline, pipeline_target: str):
    global _crawl_running, _last_manual_crawl
    _crawl_running = True
    try:
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            _crawl_executor,
            _do_crawl, crawl_pipeline, pipeline_target,
        )
        result = await asyncio.wait_for(future, timeout=_CRAWL_TIMEOUT_SECONDS)
        _last_manual_crawl = {"status": "success", **result}
    except asyncio.TimeoutError:
        _last_manual_crawl = {"status": "timeout", "error": f"Crawl exceeded {_CRAWL_TIMEOUT_SECONDS}s"}
        logger.error("Manual crawl timed out after %ds", _CRAWL_TIMEOUT_SECONDS)
    except Exception as e:
        _last_manual_crawl = {"status": "error", "error": str(e)}
        logger.error("Manual crawl failed: %s", e, exc_info=True)
    finally:
        _crawl_running = False  # ALWAYS reset

def _do_crawl(crawl_pipeline, pipeline_target: str) -> dict:
    """Sync function that runs in thread. Can raise."""
    if pipeline_target == "kehoach":
        return crawl_pipeline.run_kehoach()
    elif pipeline_target == "quydinh":
        return crawl_pipeline.run_quydinh()
    else:
        return crawl_pipeline.run()
```

**Rate limiting**: Prevent trigger spam with cooldown:

```python
_last_trigger_time: float = 0
_CRAWL_COOLDOWN_SECONDS = 60  # minimum 1 minute between triggers

@router.post("/admin/crawler/trigger")
async def trigger_crawl(...):
    global _last_trigger_time
    now = time.time()
    if _crawl_running:
        raise HTTPException(409, "Crawl đang chạy, vui lòng đợi")
    if now - _last_trigger_time < _CRAWL_COOLDOWN_SECONDS:
        remaining = int(_CRAWL_COOLDOWN_SECONDS - (now - _last_trigger_time))
        raise HTTPException(429, f"Vui lòng đợi {remaining}s trước khi trigger lại")
    _last_trigger_time = now
    # ... launch background crawl ...
```

---

### ✅ Fix 4: AnalyticsTab — Split into sub-components

**Problem**: ~300 lines + 8 recharts instances in one component → heavy initial render.

**Solution**: Split into 2 sections with lazy rendering:

```
AnalyticsTab.tsx (~80 lines)
  ├── QueryAnalyticsSection.tsx (~150 lines)  — volumes, latency, routing, top questions
  └── AgentAnalyticsSection.tsx (~120 lines)  — agent stats, tool frequency, tavily, comparison
```

Each section fetches its own data independently. `AgentAnalyticsSection` is **lazy-loaded** with `React.lazy()` since it's below the fold:

```tsx
const AgentSection = React.lazy(() => import('./AgentAnalyticsSection'));

export default function AnalyticsTab() {
  return (
    <div className="space-y-8">
      <QueryAnalyticsSection />
      <Suspense fallback={<Skeleton className="h-96" />}>
        <AgentSection />
      </Suspense>
    </div>
  );
}
```

---

### ✅ Fix 5: Empty states + Error boundaries

**Solution**: Shared `EmptyState` component + `useAdminFetch` custom hook:

```tsx
// components/admin/EmptyState.tsx
function EmptyState({ icon: Icon, title, description }: Props) {
  return (
    <div className="flex flex-col items-center py-12 text-muted-foreground">
      <Icon className="h-12 w-12 mb-4 opacity-40" />
      <p className="text-lg font-medium">{title}</p>
      <p className="text-sm">{description}</p>
    </div>
  );
}

// hooks/useAdminFetch.ts — wraps fetch with loading + error + empty detection
function useAdminFetch<T>(fetcher: () => Promise<T>, deps: any[]) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // ... useEffect with try/catch/finally ...
  // On error: toast.error() via sonner
  return { data, loading, error, refetch };
}
```

**Per-tab states:**

| State | Render |
|-------|--------|
| Loading | `Skeleton` cards/charts (shadcn) |
| Error | Red `Alert` banner + retry button |
| Empty (no data) | `EmptyState` with relevant icon + message |
| Data | Normal render |

---

## Additional Features Added

### ✅ Add 1: EP8 Audit log

User deactivation is a sensitive action → log it:

```python
@router.patch("/admin/users/{user_id}/status")
async def toggle_user_status(...):
    # ... update is_active ...
    # Audit log entry
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {"is_active": body.is_active},
            "$push": {"audit_log": {
                "action": "deactivate" if not body.is_active else "activate",
                "by": str(current_user.id),
                "at": datetime.utcnow(),
            }},
        },
    )
```

---

### ✅ Add 2: EP2 configurable `days` param

```python
@router.get("/admin/stats/users")
async def get_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    sort_by: str = Query("created_at"),
    order: str = Query("desc"),
    days: int | None = Query(None, ge=1, le=365),  # filter users active in last N days
):
    # if days: add $match {"last_login_at": {"$gte": N_days_ago}}
```

---

### ✅ Add 3: EP9 cooldown rate limiting

(See Fix 3 above — 60s cooldown between triggers)

---

### ✅ Add 4: Top Questions pagination (EP4)

```python
@router.get("/admin/stats/queries")
async def get_query_analytics(
    days: int = Query(30, ge=1, le=365),
    top_questions_limit: int = Query(15, ge=5, le=50),  # configurable
):
```

---

### Deferred (Nice-to-have, not in scope)

| Feature | Reason for deferral |
|---------|--------------------|
| Export CSV/JSON | Can add later as a separate button per table; not blocking |
| Notification on crawl complete | Requires notification infra changes |

---

## Phase Breakdown (Updated)

### Phase 1: Backend + Overview + Users

#### Files to create/modify

| # | Action | File | Est. lines | Notes |
|---|--------|------|-----------|-------|
| 1 | **NEW** | [admin_stats.py](file:///d:/GR/src/RAG_v2/api/routes/admin_stats.py) | ~450 | 10 endpoints, all `require_admin` |
| 2 | **MODIFY** | [main.py](file:///d:/GR/src/RAG_v2/api/main.py) | +3 | Include router + version check |
| 3 | **NEW** | [adminStats.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/types/adminStats.ts) | ~100 | All response interfaces |
| 4 | **MODIFY** | [adminApi.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/services/adminApi.ts) | +70 | 10 new API functions |
| 5 | **NEW** | [useAdminFetch.ts](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/hooks/useAdminFetch.ts) | ~40 | Shared fetch hook |
| 6 | **NEW** | [EmptyState.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/EmptyState.tsx) | ~25 | Shared empty state |
| 7 | **NEW** | [OverviewTab.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/OverviewTab.tsx) | ~130 | 6 KPI cards + states |
| 8 | **NEW** | [UsersTab.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/components/admin/UsersTab.tsx) | ~300 | Table + charts + toggle |
| 9 | **MODIFY** | [AdminPage.tsx](file:///d:/GR/src/RAG_v2/frontend/chat-companion/src/pages/AdminPage.tsx) | refactor | 6-tab layout, stubs for P2/P3 |

#### Endpoints detail

| EP | Method | Path | Key fix |
|----|--------|------|---------|
| 1 | GET | `/admin/stats/overview` | — |
| 2 | GET | `/admin/stats/users` | `$toString` for ObjectId join + `days` param |
| 3 | GET | `/admin/stats/users/breakdown` | — |
| 4 | GET | `/admin/stats/queries` | Version-guarded `$percentile` + configurable `top_questions_limit` |
| 5 | GET | `/admin/stats/agent` | — |
| 6 | GET | `/admin/stats/feedback/topics` | — |
| 7 | GET | `/admin/stats/system` | — |
| 8 | PATCH | `/admin/users/{id}/status` | `$push audit_log` |
| 9 | POST | `/admin/crawler/trigger` | Timeout 10min + try/finally + 60s cooldown |
| 10 | GET | `/admin/crawler/status` | — |

#### Verification

```bash
# RBAC
curl -H "Authorization: Bearer <student>" localhost:8000/admin/stats/overview  # → 403

# Data integrity
curl -H "Authorization: Bearer <admin>" localhost:8000/admin/stats/overview
# Compare total_users=7, total_sessions=440, total_queries=947 with MongoDB

# EP2 join
curl -H "Authorization: Bearer <admin>" "localhost:8000/admin/stats/users?limit=3"
# Verify session_count > 0 for active users (not all zeros)

# EP9 cooldown
curl -X POST -H "Authorization: Bearer <admin>" localhost:8000/admin/crawler/trigger
# Immediate second call → 429
```

---

### Phase 2: Analytics + System + Crawler UI

#### Files to create/modify

| # | Action | File | Est. lines |
|---|--------|------|-----------|
| 1 | **NEW** | `components/admin/AnalyticsTab.tsx` | ~80 |
| 2 | **NEW** | `components/admin/QueryAnalyticsSection.tsx` | ~150 |
| 3 | **NEW** | `components/admin/AgentAnalyticsSection.tsx` | ~120 |
| 4 | **NEW** | `components/admin/SystemTab.tsx` | ~230 |
| 5 | **MODIFY** | `pages/AdminPage.tsx` | +4 lines (remove stubs) |

#### Key UI elements

**QueryAnalyticsSection:**
- Days selector: `Select` (7/30/90)
- Query Volume: `AreaChart`
- Latency Trend: `LineChart` (avg + p95, p95 = null nếu MongoDB < 7.0)
- Routing: `PieChart` (intent) + `BarChart` (mode/route)
- Top Questions: `Table` (sortable, configurable limit)
- Error count: `Badge`

**AgentAnalyticsSection** (lazy loaded):
- Stats cards: total calls, avg iterations, error rate, tavily triggers
- Tool Frequency: `BarChart`
- Daily Usage: `BarChart`
- Agent vs Classic: comparison cards

**SystemTab:**
- Config: grid of cards with enable/disable badges
- Cache: `Progress` bar + numbers
- Documents: `BarChart` (by status) + `PieChart` (by collection)
- Crawler: schedule info + trigger button + status + last crawl result
  - `Select` for pipeline (all/kehoach/quydinh)
  - Loading spinner when `is_running`
  - Auto-poll `getCrawlerStatus()` every 5s while running

#### Verification

```
# AnalyticsTab
- Switch days → all charts update
- Agent section lazy loads only when scrolled into view
- Empty database → EmptyState shown, not crash

# SystemTab
- Crawler trigger → button disabled → spinner → result shown
- Double-click → 429 toast "Đợi Xs"
- While running → status shows "đang chạy" with spinner
```

---

### Phase 3: Enhanced Feedback

#### Files to create/modify

| # | Action | File | Est. lines |
|---|--------|------|-----------|
| 1 | **NEW** | `components/admin/FeedbackTab.tsx` | ~260 |
| 2 | **MODIFY** | `pages/AdminPage.tsx` | -160, +2 (remove inline, import) |

#### Enhancements over current

| Feature | Current | Phase 3 |
|---------|---------|---------|
| Stats cards | 4 cards | 5 cards (+Response Rate) |
| Satisfaction trend | ❌ | AreaChart daily |
| Disliked topics | ❌ | Table top 20, category badges |
| Feedback detail | Truncated inline | Dialog with full Q/A/comment |
| States | Basic loading | Loading + empty + error |

#### Verification

```
# Satisfaction trend renders with data
# Empty collection → "Chưa có feedback" message
# Click row → Dialog opens with full content
# Category badges show correct counts
```

---

## Complete File List

| Phase | New files | Modified files | Total changes |
|-------|-----------|----------------|--------------|
| **1** | 6 new | 3 modified | 9 files |
| **2** | 4 new | 1 modified | 5 files |
| **3** | 1 new | 1 modified | 2 files |
| **Total** | **11 new** | **5 modified** | **16 files** |

### No new npm dependencies needed

| Already installed | Version | Used for |
|------------------|---------|----------|
| `recharts` | ^2.15.4 | All charts |
| `chart.tsx` (shadcn) | — | Chart wrapper |
| `lucide-react` | 0.462.0 | Icons |
| `date-fns` | 4.1.0 | Date formatting |
| shadcn/ui | 49 components | Card, Table, Dialog, Progress, Switch, Select, Badge, Skeleton, Alert |
