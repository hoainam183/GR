# Module: `tests`

Source-verified: 2026-05-22 from `tests/*.py`, root test files, and pytest config.

## Purpose

`tests` contains regression, unit, contract, and integration-style tests for backend RAG, API routes, Redis/cache behavior, auth/RBAC, mobile contracts, upload pipeline, retrieval, and evaluation.

Pytest config is in `pytest.ini`.

## Main Test Areas

| Files | Area |
| --- | --- |
| `test_agent_langgraph.py`, `test_adapters.py`, `test_constants.py` | Agent graph/tools/constants. |
| `test_chat_route_mode.py`, `test_response_mapper.py`, `test_dependencies.py` | API chat routing, mapper, dependencies. |
| `test_admin_llm_config.py` | Persisted admin LLM config, startup merge, endpoint ordering, pipeline reload. |
| `test_upload_api.py`, `test_document_pipeline.py`, `test_storage.py` | Admin upload/document pipeline/storage. |
| `test_rbac.py` | Auth and admin/superadmin behavior. |
| `test_phase1_redis.py`, `test_phase2_redis.py` | Redis session/history/cache/rate limit behavior. |
| `test_phase7.py`, `test_phase8.py` | Recent RAG/Tavily/profile/freshness guardrails. |
| `retrieval/test_*.py` | Retrieval module unit/regression checks moved out of runtime package. |
| `test_reference_resolver.py`, `test_multi_collection_fusion.py` | Retrieval post-processing/fusion. |
| `test_mobile_api_contracts.py` | Backend contract for mobile/shared API. |
| `test_two_layer_eval.py`, `test_week4_evaluate.py` | Evaluation layer. |
| `conversation_regression_queries.jsonl` | Saved chat/RAG regression prompts. |

Root-level test files such as `test_reflection.py`, `test_retrieval.py`, and `test_retrieval_docs.py` are legacy/manual checks outside the default pytest `testpaths`; retrieval pytest files should stay under `tests/retrieval/`.

## Markers

Configured markers:

- `integration`
- `e2e`

Use `-m "not integration"` for fast local checks that should not require external services/models.

## Maintenance Notes

- When fixing chat/RAG behavior, add or replay saved conversation regression queries.
- Keep mobile contract tests aligned with `packages/shared` and backend schemas.
- Keep RAGPipeline admin reload tests aligned with the current hot-swap contract; route cache is cleared on reload, but reflection no longer has a separate pipeline cache.
- Prefer focused tests for doc-only changes only when there is parser/link/script impact.
- For retrieval/model/service tests, be explicit about whether Qdrant/ES/Mongo/Redis/local models are required.

## Useful Commands

```bash
python -m pytest tests -q -m "not integration"
python -m pytest tests/retrieval -q -m "not integration"
python -m pytest tests/test_chat_route_mode.py tests/test_response_mapper.py -q -m "not integration"
python -m pytest tests/test_upload_api.py tests/test_document_pipeline.py -q -m "not integration"
```
