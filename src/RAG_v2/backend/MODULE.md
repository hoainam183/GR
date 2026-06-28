# Module: `backend`

Source-verified: 2026-06-24 from `backend/main.py`, `api/main.py`.

## Purpose

`backend` is a **legacy compatibility shim** — not the real application. Its sole job is to let old entry-point commands (`python src/RAG_v2/backend/main.py` or `uvicorn src.RAG_v2.backend.main:app`) still reach the current FastAPI app, which lives entirely inside `api/`.

`backend` owns nothing: no routes, no lifespan, no settings, no pipeline. All of that lives in `api/main.py` (`create_app()` + `lifespan`).


## File Map

```text
backend/
  main.py     Inserts RAG_v2 root into sys.path, re-exports `app` from api.main,
              and runs uvicorn on 0.0.0.0:8000 under __main__.

```

## Public Symbols

### `main.py`

```python
# module-level re-export
from api.main import app  # app: FastAPI instance created by api.main.create_app()
```

- `app` is the only symbol exposed. It is not created here; it is imported from `api.main`.
- When run as `__main__`, starts uvicorn with **hardcoded** `host="0.0.0.0"`, `port=8000` — these are NOT read from `Settings`. If the port or bind address needs to change, edit the deployment command directly or update `api/main.py`.
- Path wiring: `_RAG_V2_ROOT = Path(__file__).resolve().parent.parent` (i.e. `src/RAG_v2/`). This is inserted at index 0 in `sys.path` on import, allowing `api.main` and all sibling packages to be found.



## How `backend` Relates to `api`

```
Legacy command
  └─ backend/main.py
       ├─ sys.path.insert(RAG_v2 root)
       └─ from api.main import app   ──► api/main.py
                                           ├─ create_app()   (routes, middleware, CORS)
                                           └─ lifespan()     (Settings, RAGPipeline,
                                                              MongoLogger, Redis,
                                                              auto-crawl scheduler)
```

`api/main.py` is where `create_app()` assembles the 12 route groups, adds CORS and rate-limit middleware, and `lifespan()` wires in `RAGPipeline`, `MongoLogger`, Redis caches, and the APScheduler auto-crawl job. None of that logic touches `backend/`.

## Maintenance Notes

- Do not add routes, middleware, or business logic to `backend/`. Everything belongs in `api/`.
- The hardcoded `host="0.0.0.0", port=8000` in `main.py` is a known limitation. Production deployments that need a different port must use the uvicorn CLI directly against `api.main:app`.

- If the `api/` entrypoint ever moves, update the import in `backend/main.py` and the sys.path logic accordingly.

## Useful Checks

```bash
# Confirm the re-export resolves correctly
python -c "from src.RAG_v2.backend.main import app; print(app.title)"
# Expected: RAG v2 Chatbot API

```
