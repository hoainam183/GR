# Redis Improvement Plan — RAG System

> Dựa trên code review `session_store.py`, `llm_cache.py`, `history_cache.py`, `rate_limiter.py`  
> Overall score: **8.5/10** — Production-ready với các cải tiến dưới đây

---

## Tóm tắt nhanh

| # | Vấn đề | File | Độ ưu tiên | Effort |
|---|--------|------|-----------|--------|
| 1 | `invalidate_all()` → tag-based invalidation | `llm_cache.py` | 🔴 Cao | ~2h |
| 2 | Zombie session IDs trong Sorted Set | `session_store.py` | 🟡 Trung bình | ~1h |
| 3 | Race condition check vs record | `rate_limiter.py` | 🟡 Trung bình | ~1.5h |
| 4 | Embedding vector cache | `embed_cache.py` (mới) | 🟡 Trung bình | ~1.5h |
| 5 | Hit/Miss metrics endpoint | `llm_cache.py` + router | 🟢 Nice | ~1h |
| 6 | Redis connection pool config | `settings.py` | 🟢 Nice | ~30m |

---

## Fix 1 — Tag-based Cache Invalidation 🔴

**File:** `llm_cache.py`

### Vấn đề hiện tại

`invalidate_all()` dùng `SCAN` để xóa toàn bộ `llm_cache:*` mỗi khi có document mới.  
Document mới về topic A vô tình xóa cache của topic B, C, D — lãng phí hoàn toàn.

```python
# ❌ Hiện tại — nuclear option
async def invalidate_all(self):
    async for key in redis.scan_iter("llm_cache:*"):
        await redis.delete(key)
```

### Fix

Mỗi cache entry lưu kèm tag là danh sách `doc_id` đã dùng.  
Khi document thay đổi, chỉ xóa cache entries có chứa doc đó.

```python
# ✅ Sau fix — tag-based invalidation

async def set(self, fingerprint: str, answer: str, doc_ids: list[str]):
    cache_key = f"llm_cache:{fingerprint}"

    pipeline = redis.pipeline()
    pipeline.setex(cache_key, self.DEFAULT_TTL, answer)

    # Tag: doc_id → set các cache keys liên quan
    for doc_id in doc_ids:
        tag_key = f"doc_cache_tag:{doc_id}"
        pipeline.sadd(tag_key, cache_key)
        pipeline.expire(tag_key, 86400)  # tag tự expire sau 24h

    await pipeline.execute()


async def invalidate_by_doc(self, doc_id: str):
    """Chỉ xóa cache liên quan đến document vừa được crawl mới."""
    tag_key    = f"doc_cache_tag:{doc_id}"
    cache_keys = await redis.smembers(tag_key)

    if not cache_keys:
        return 0

    pipeline = redis.pipeline()
    for key in cache_keys:
        pipeline.unlink(key)        # UNLINK thay DEL — async, non-blocking
    pipeline.delete(tag_key)
    await pipeline.execute()

    return len(cache_keys)          # trả về số entries đã xóa để log


# Gọi khi crawler hoàn thành
invalidated = await llm_cache.invalidate_by_doc(doc_id="doc_abc_123")
logger.info(f"Invalidated {invalidated} cache entries for doc doc_abc_123")
```

### Giữ lại invalidate_all() cho trường hợp cần reset toàn bộ

```python
async def invalidate_all(self):
    """Dùng khi cần reset toàn bộ — ví dụ: đổi LLM model, reindex toàn bộ."""
    count = 0
    pipeline = redis.pipeline()
    async for key in redis.scan_iter("llm_cache:*", count=100):
        pipeline.unlink(key)
        count += 1
        if count % 100 == 0:
            await pipeline.execute()
            pipeline = redis.pipeline()
    await pipeline.execute()
    logger.warning(f"Full cache invalidation: {count} entries removed")
```

---

## Fix 2 — Zombie Session Cleanup 🟡

**File:** `session_store.py`

### Vấn đề hiện tại

`session:{id}` Hash có TTL 7 ngày — tự expire.  
`user_sessions:{user_id}` Sorted Set **không có TTL** → tích lũy session IDs zombie (hash đã expire, ID vẫn còn trong Set).

```python
# Sau 1 năm, user_sessions:user_123 có thể chứa hàng trăm zombie IDs
```

### Fix — Lazy cleanup khi fetch

```python
# ✅ Trong get_user_sessions() — filter và cleanup zombie
async def get_user_sessions(self, user_id: str) -> list[dict]:
    zset_key    = f"user_sessions:{user_id}"
    session_ids = await redis.zrevrange(zset_key, 0, 49)  # lấy 50, filter sau

    if not session_ids:
        return []

    # Batch fetch tất cả session hashes
    pipeline = redis.pipeline()
    for sid in session_ids:
        pipeline.hgetall(f"session:{sid}")
    results = await pipeline.execute()

    valid_sessions = []
    zombie_ids     = []

    for sid, data in zip(session_ids, results):
        if data:
            valid_sessions.append(data)
        else:
            zombie_ids.append(sid)   # hash đã expire → zombie

    # Cleanup zombie IDs khỏi Sorted Set (async, không chờ)
    if zombie_ids:
        asyncio.create_task(
            redis.zrem(zset_key, *zombie_ids)
        )
        logger.debug(f"Cleaned {len(zombie_ids)} zombie session IDs for {user_id}")

    return valid_sessions
```

### Fix — Giới hạn kích thước Sorted Set

```python
# ✅ Khi tạo session mới — trim Sorted Set, chỉ giữ 100 sessions gần nhất
async def create_session(self, user_id: str, session_id: str, title: str):
    zset_key = f"user_sessions:{user_id}"
    score    = int(datetime.utcnow().timestamp())

    pipeline = redis.pipeline()
    pipeline.hset(f"session:{session_id}", mapping={
        "user_id": user_id, "title": title,
        "created_at": score, "updated_at": score, "turn_count": 0
    })
    pipeline.expire(f"session:{session_id}", 7 * 86400)  # TTL 7 ngày
    pipeline.zadd(zset_key, {session_id: score})
    pipeline.zremrangebyrank(zset_key, 0, -101)          # giữ tối đa 100 sessions
    await pipeline.execute()
```

---

## Fix 3 — Atomic Rate Limiter với Lua Script 🟡

**File:** `rate_limiter.py`

### Vấn đề hiện tại

`check()` và `record()` tách riêng → race condition: 2 requests đồng thời cùng pass check → cả hai record → vượt limit.

### Fix — Tạo file `rate_limit.lua`

```lua
-- rate_limit.lua
-- KEYS[1]: Redis key (e.g. rate:min:user_123)
-- ARGV[1]: now (milliseconds)
-- ARGV[2]: window size (milliseconds)
-- ARGV[3]: limit
-- ARGV[4]: TTL (seconds)
-- Returns: {allowed (0/1), current_count, limit, warning (0/1)}

local key       = KEYS[1]
local now       = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit     = tonumber(ARGV[3])
local ttl_s     = tonumber(ARGV[4])

-- Xóa entries cũ ngoài cửa sổ thời gian
redis.call('ZREMRANGEBYSCORE', key, 0, now - window_ms)

-- Đếm requests hiện tại
local count = redis.call('ZCARD', key)

-- Kiểm tra giới hạn
if count >= limit then
    return {0, count, limit, 0}
end

-- Ghi request hiện tại (atomic với check)
redis.call('ZADD', key, now, tostring(now))
redis.call('EXPIRE', key, ttl_s)

local new_count = count + 1
local warning   = 0
if new_count >= math.floor(limit * 0.8) then
    warning = 1   -- đạt 80% ngưỡng
end

return {1, new_count, limit, warning}
```

### Cập nhật `rate_limiter.py`

```python
# ✅ Load Lua script khi startup — tránh load lại mỗi request
class SlidingWindowRateLimiter:

    def __init__(self, redis_client, rpm_limit: int, rpd_limit: int):
        self.redis     = redis_client
        self.rpm_limit = rpm_limit
        self.rpd_limit = rpd_limit
        self._sha_rpm  = None  # SHA của Lua script sau khi load
        self._sha_rpd  = None

    async def startup(self):
        """Gọi khi FastAPI lifespan startup."""
        script      = Path("rate_limit.lua").read_text()
        self._sha   = await self.redis.script_load(script)

    async def check_and_record(self, identifier: str) -> dict:
        now_ms = int(time.time() * 1000)

        # Check RPM
        allowed_rpm, count_rpm, _, warn_rpm = await self.redis.evalsha(
            self._sha, 1,
            f"rate:min:{identifier}",
            now_ms, 60_000, self.rpm_limit, 120
        )

        if not allowed_rpm:
            return {"allowed": False, "reason": "rpm_exceeded",
                    "count": count_rpm, "limit": self.rpm_limit}

        # Check RPD
        allowed_rpd, count_rpd, _, warn_rpd = await self.redis.evalsha(
            self._sha, 1,
            f"rate:day:{identifier}",
            now_ms, 86_400_000, self.rpd_limit, 86_400
        )

        if not allowed_rpd:
            return {"allowed": False, "reason": "rpd_exceeded",
                    "count": count_rpd, "limit": self.rpd_limit}

        # Cảnh báo sớm
        if warn_rpm or warn_rpd:
            logger.warning(f"Rate limit warning for {identifier}: "
                           f"RPM {count_rpm}/{self.rpm_limit}, "
                           f"RPD {count_rpd}/{self.rpd_limit}")

        return {"allowed": True, "rpm": count_rpm, "rpd": count_rpd}
```

> **Note:** Với Lua script, check và record là atomic — không còn race condition.  
> Trade-off: mọi request đều tính quota kể cả khi LLM fail sau đó.  
> Nếu muốn giữ record-after-success, chấp nhận race condition nhỏ là hợp lý với traffic thấp.

---

## Fix 4 — Embedding Vector Cache 🟡

**File:** `embed_cache.py` (tạo mới)

### Động lực

Mỗi request gọi embedding API (Gemini/OpenAI) tốn ~100–300ms và chi phí token.  
Câu hỏi tương tự hoặc lặp lại không cần embed lại.

```python
# embed_cache.py

import hashlib, json
from typing import Optional


class EmbeddingCache:

    PREFIX  = "embed"
    TTL     = 86_400        # 24h — embedding ổn định, ít thay đổi

    def __init__(self, redis_client, embedding_fn):
        self.redis        = redis_client
        self.embedding_fn = embedding_fn  # callable: text → list[float]

    def _key(self, text: str) -> str:
        normalized = text.lower().strip()
        return f"{self.PREFIX}:{hashlib.sha256(normalized.encode()).hexdigest()}"

    async def get_or_compute(self, text: str) -> list[float]:
        key    = self._key(text)
        cached = await self.redis.get(key)

        if cached:
            await self.redis.incr("cache:stats:embed:hit")
            return json.loads(cached)

        await self.redis.incr("cache:stats:embed:miss")

        # Compute embedding
        vector = await self.embedding_fn(text)

        # Cache kết quả
        await self.redis.setex(key, self.TTL, json.dumps(vector))
        return vector
```

### Tích hợp vào RAG pipeline

```python
# rag_pipeline.py
embed_cache = EmbeddingCache(redis_client, embedding_fn=gemini.embed)

async def process_query(query: str) -> str:
    # Trước: gọi trực tiếp embedding API
    # vector = await gemini.embed(query)

    # Sau: qua cache
    vector = await embed_cache.get_or_compute(query)

    # ... tiếp tục Qdrant search
```

---

## Fix 5 — Cache Metrics Endpoint 🟢

**File:** `llm_cache.py` + `routers/metrics.py`

```python
# Trong llm_cache.py — thêm tracking vào get() và set()

async def get(self, fingerprint: str) -> Optional[str]:
    result = await self.redis.get(f"llm_cache:{fingerprint}")
    # Track hit/miss
    stat_key = "cache:stats:llm:hit" if result else "cache:stats:llm:miss"
    await self.redis.incr(stat_key)
    return result


# routers/metrics.py
@router.get("/metrics/cache")
async def cache_metrics():
    keys = [
        "cache:stats:llm:hit",   "cache:stats:llm:miss",
        "cache:stats:embed:hit", "cache:stats:embed:miss",
    ]
    values = await redis.mget(*keys)
    hit_llm, miss_llm, hit_emb, miss_emb = [int(v or 0) for v in values]

    def hit_rate(h, m): return round(h / (h + m) * 100, 1) if (h + m) else 0

    return {
        "llm_cache":    {"hit": hit_llm,  "miss": miss_llm,
                         "hit_rate": f"{hit_rate(hit_llm, miss_llm)}%"},
        "embed_cache":  {"hit": hit_emb,  "miss": miss_emb,
                         "hit_rate": f"{hit_rate(hit_emb, miss_emb)}%"},
    }
```

---

## Fix 6 — Redis Connection Pool Config 🟢

**File:** `settings.py`

```python
# ✅ Explicit config — không dùng default của redis-py

import redis.asyncio as aioredis

redis_client = aioredis.from_url(
    settings.REDIS_URL,
    max_connections=20,          # tối đa concurrent connections
    socket_timeout=2.0,          # 2s timeout mỗi command
    socket_connect_timeout=5.0,  # 5s để establish connection
    retry_on_timeout=True,
    health_check_interval=30,    # ping mỗi 30s để detect stale connection
    decode_responses=True,
)

# .env
# REDIS_MAX_CONNECTIONS=20
# REDIS_SOCKET_TIMEOUT=2.0
# REDIS_CONNECT_TIMEOUT=5.0
```

---

## Thứ tự triển khai

```
Tuần 1
├── Fix 1: Tag-based invalidation       (~2h)  ← impact lớn nhất
└── Fix 6: Connection pool config       (~30m) ← nhanh, rủi ro thấp

Tuần 2
├── Fix 2: Zombie session cleanup       (~1h)
└── Fix 5: Metrics endpoint             (~1h)

Tuần 3
├── Fix 3: Lua rate limiter             (~1.5h)
└── Fix 4: Embedding cache              (~1.5h)
```

---

## Checklist hoàn thành

- [ ] **Fix 1** — Tag-based invalidation trong `llm_cache.py`
- [ ] **Fix 2** — Zombie cleanup trong `get_user_sessions()`
- [ ] **Fix 2** — ZREMRANGEBYRANK khi tạo session mới
- [ ] **Fix 3** — Tạo `rate_limit.lua`, cập nhật `rate_limiter.py`
- [ ] **Fix 3** — Gọi `await rate_limiter.startup()` trong FastAPI lifespan
- [ ] **Fix 4** — Tạo `embed_cache.py`, tích hợp vào RAG pipeline
- [ ] **Fix 5** — Thêm INCR tracking vào `llm_cache.get()`
- [ ] **Fix 5** — Tạo `GET /metrics/cache` endpoint
- [ ] **Fix 6** — Cập nhật Redis client config trong `settings.py`

---

*Generated from code review — Redis RAG System*