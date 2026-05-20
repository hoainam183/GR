# Module: `schemas`

Source-verified: 2026-05-20 from `schemas/*.py`, `api/routes/*.py`, and `packages/shared`.

## Purpose

`schemas` defines Pydantic API contracts shared by FastAPI routes and response mappers. This is the backend source of truth for request/response shape.

## File Map

```text
schemas/
  __init__.py       Public schema exports.
  chat.py           Chat request/response, retrieved docs, trace payload, health response.
  constants.py      Route/mode constants and CLARIFY_SENTINEL.
  document.py       Admin upload/document/chunk review schemas.
  mobile.py         Bookmark, feedback, notification, lookup schemas.
  user.py           Auth/profile/token/admin schemas.
```

## Chat Schemas

`chat.py` includes:

- `HistoryMessage`
- `UserContext`
- `ChatRequest`
- `RetrievedDocument`
- `CollectionScore`
- `FilterInfo`
- `CollectionResult`
- `AgentToolCall`
- `AgentTracePayload`
- `ChatResponse`
- `HealthResponse`

`ChatRequest` supports:

- `question`
- `mode`: `auto`, `rag`, `agent`
- `top_k`
- `history`
- `session_id`
- `user_context`
- `user_id`

Authenticated routes should derive identity from JWT instead of trusting body identity.

## Document Schemas

`document.py` supports admin upload/review:

- upload request
- document detail/list response
- chunk preview/list response
- Markdown/cleaned text content wrappers

Keep this aligned with `models/document.py`, `models/document_chunk.py`, and admin UI types.

## Mobile Schemas

`mobile.py` supports:

- bookmark create/update/folder operations
- feedback create
- notification subscribe/unsubscribe
- lookup document
- internal notification creation

## User Schemas

`user.py` supports:

- manual registration/login
- user profile update
- public user response
- token response
- admin creation

`UserPublic` should stay aligned with `packages/shared/src/types/auth.ts`.

## Constants

`constants.py` contains route/mode constants and `CLARIFY_SENTINEL`. Agent clarification code depends on the sentinel string.

## Maintenance Notes

- Schema changes are public API changes. Update `api/response_mapper.py`, web/mobile/shared TypeScript types, and tests.
- Prefer additive fields with sensible defaults when possible.
- Keep trace/debug fields optional; pipeline outputs can vary by route/mode/fallback.

## Useful Checks

```bash
python -m py_compile schemas/*.py
python -m pytest tests/test_response_mapper.py tests/test_mobile_api_contracts.py -q -m "not integration"
```
