# Module: `models`

Source-verified: 2026-05-20 from `models/*.py`, `api/main.py`, and auth/admin route usage.

## Purpose

`models` owns MongoDB access, durable chat logging, user and document Pydantic models, and admin upload document/chunk shapes. It is the persistence boundary for FastAPI routes and pipeline logging.

There are two MongoDB access styles:

- Async Motor access in `database.py` for FastAPI dependencies/routes.
- Sync PyMongo-style logging in `mongo_logger.py` for sessions, turns, query logs, and agent traces.

## File Map

```text
models/
  database.py        Motor singleton, async DB dependency, index creation.
  mongo_logger.py    Sync durable logging for sessions/turns/query logs/agent traces.
  user.py            UserDocument and PyObjectId helpers.
  document.py        DocumentRecord and AuditEntry for admin upload pipeline.
  document_chunk.py  DocumentChunk review/indexing model.
```

## Mongo Collections

Main collections used by this codebase:

| Collection | Owner | Purpose |
| --- | --- | --- |
| `users` | `auth`, `routers/auth.py` | Accounts, role, profile, HUST metadata. |
| `sessions` | `MongoLogger`, `api/routes/session.py` | Chat session metadata. |
| `turns` | `MongoLogger` | User/assistant turns with sources/metadata. |
| `query_logs` | `MongoLogger` | Flat analytics log per turn. |
| `agent_traces` | `MongoLogger` | LangGraph/agent traces. |
| `documents` | `DocumentPipeline`, upload routes | Admin-uploaded document records. |
| `document_chunks` | `DocumentPipeline`, upload routes | Reviewable chunks before/after indexing. |
| `bookmarks` | `api/routes/bookmark.py` | Mobile/web saved answer snapshots. |
| `bookmark_folders` | `api/routes/bookmark.py` | User bookmark folders. |
| `feedback` | `api/routes/feedback.py` | Answer ratings/comments. |
| `notifications` | `api/routes/notification.py` | User notification inbox. |
| `notification_subscriptions` | `api/routes/notification.py` | Push token/topic subscriptions. |

## `database.py`

Responsibilities:

- Resolve Mongo URI/database from `Settings`.
- Keep a process-wide Motor client singleton.
- Provide `get_database()` FastAPI dependency.
- Close the Motor client on shutdown.
- Create indexes for users, sessions, turns, query logs, agent traces, mobile features, and document records.
- Use safe index creation helpers so stale/conflicting indexes can be dropped and recreated where needed.

Use this module for async route-level DB work.

## `mongo_logger.py`

Responsibilities:

- `new_session(user_id=None)`
- `get_session(session_id)`
- `list_sessions(user_id, limit)`
- `delete_session(session_id)`
- `update_session_title(session_id, title)`
- `log_turn(...)`
- `get_turns(session_id)`
- `get_history(session_id)`
- `log_agent_trace(session_id, trace_dict)`
- `get_agent_stats(limit)`

`log_turn()` writes session counters/metadata, turn documents, query logs, and can sync Redis history/session state when the cache layer is attached.

## User Model

`UserDocument` contains authentication/profile fields used across auth, chat, and mobile:

- `id`
- `email`
- `username`
- `hashed_password`
- `role`
- `student_id`
- `full_name`
- `cohort`
- `major`
- `major_code`
- timestamps

`PyObjectId` supports Pydantic v1/v2 style validation.

## Document Models

`DocumentRecord` tracks admin upload lifecycle:

```text
uploaded -> converting -> converted -> cleaning -> cleaned
-> chunking -> chunked -> embedding -> indexed
```

It also stores collection, converter/chunker choices, file paths, chunk counts, indexed counts, audit entries, and error/status messages.

`DocumentChunk` stores reviewable chunk content/metadata, selected state, strategy, and source document id.

## Maintenance Notes

- Keep Mongo index names and fields aligned with route query patterns.
- Do not use `MongoLogger` for async FastAPI dependency reads unless the route already expects sync behavior.
- For chat/session contract changes, update `cache/session_store.py`, `api/routes/session.py`, and shared frontend/mobile types.
- For document status changes, update `schemas/document.py`, `api/routes/upload.py`, and `pipeline/document_pipeline.py`.

## Useful Checks

```bash
python -m py_compile models/*.py
python -m pytest tests/test_mongo.py tests/test_week4_mongo_logger.py tests/test_storage.py -q -m "not integration"
```
