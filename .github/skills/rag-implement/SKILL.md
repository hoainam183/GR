---
name: rag-implement
description: "RAG_v2 implement-and-test workflow. Use when: you have a rough idea or prompt for a change to src/RAG_v2 and want the agent to (1) read the actual codebase, (2) rewrite your prompt into a precise, grounded spec, (3) implement following clean-arch rules, (4) run tests. Triggers: 'implement', 'add feature', 'refactor RAG', 'I want to', 'rough idea', any vague request about RAG_v2 code."
argument-hint: "Describe your rough idea, e.g. 'add streaming support to the pipeline'"
---

# RAG_v2 — Implement & Test Workflow

## Purpose
Turn a rough user prompt into a grounded, precise spec, implement it correctly
against the real `src/RAG_v2` codebase, then verify with tests.

---

## Step 1 — Read the Codebase (always first)

Before writing a single line of code, explore the relevant parts of `src/RAG_v2/`:

1. List the top-level folder to see all modules.
2. For every module touched by the request, read:
   - `<module>/base.py` — the ABC / interface
   - `<module>/__init__.py` — the factory & registry
   - Any concrete file that will be modified or extended
3. Read `config/settings.py` to see what env vars already exist.
4. Read `pipeline/rag_pipeline.py` and `pipeline/flows.py` to understand
   the wiring.
5. Read the relevant test files under `tests/`.

**Do not skip this step even for small changes.**

---

## Step 2 — Rewrite the Prompt

After reading the code, rewrite the user's rough request as a precise spec:

```
REWRITTEN SPEC
==============
Goal         : <one sentence — what changes>
Files to add : <list exact paths, e.g. src/RAG_v2/llm/openai_llm.py>
Files to edit: <list exact paths + which section changes>
Settings     : <new env vars to add to Settings and .env.example>
Interface    : <method signatures that must be implemented or changed>
Tests        : <which test file, what scenario to cover>
No-change    : <list files that must NOT change>
```

Show this spec to the user and ask for a quick confirm before continuing.
If the spec is obviously correct (e.g. user says "yes, exactly"), proceed
immediately without asking again.

---

## Step 3 — Implement (clean-arch rules)

Follow the `python-rag-clean-arch` skill rules strictly:

- **ABCs first** — if a new component type is needed, add `base.py` before
  the concrete class.
- **Lazy factory** — register with `@register_<component>("<name>")` decorator;
  add to `_PROVIDER_MODULES` dict in `__init__.py`.
- **Settings** — new credentials/flags go only in `config/settings.py` with
  empty-string defaults; document in `.env.example`.
- **Pipeline** — `pipeline/rag_pipeline.py` calls only factory functions,
  never concrete constructors.
- **Prompts** — all prompt text lives in `llm/prompts.py`; no prompt strings
  inside concrete provider files.
- **No extra scope** — implement exactly the spec from Step 2, nothing more.

Implement in this order:
1. `base.py` (if new ABC needed)
2. `config/settings.py` additions
3. `.env.example` additions
4. Concrete implementation file(s)
5. `__init__.py` factory registration
6. Pipeline wiring (if needed)

---

## Step 4 — Run Tests

After implementation, always run tests:

```bash
# From workspace root, activate venv first
source /Users/nam.nguyen/GR/.venv/bin/activate

# Run only the relevant test module first (fast feedback)
python -m pytest src/RAG_v2/tests/<relevant_test>.py -v

# If that passes, run the full test suite
python -m pytest src/RAG_v2/tests/ -v --tb=short
```

If tests fail:
1. Read the error output carefully.
2. Fix the root cause (do NOT delete or skip failing tests).
3. Re-run until all tests pass.
4. If a test was clearly written for the old interface, update it to match
   the new interface — but confirm the change is intentional first.

After tests pass, run a quick type check:

```bash
python -m mypy src/RAG_v2/llm/ src/RAG_v2/embedding/ src/RAG_v2/reranking/ src/RAG_v2/pipeline/ --ignore-missing-imports
```

---

## Step 5 — Report

Summarise what was done:

```
DONE
====
Added   : <file list>
Edited  : <file list>
Env vars: <list>
Tests   : <passed / N tests>
Mypy    : <clean / warnings>
To activate: set <ENV_VAR>=<value> in .env
```

---

## Quality Gates

Before marking done, verify:
- [ ] `isinstance(obj, BaseXxx)` is `True` for every new concrete class
- [ ] No concrete class is imported outside its factory `__init__.py`
- [ ] All abstract methods implemented (no `NotImplementedError` left)
- [ ] `.env.example` updated with new keys
- [ ] Tests pass with `FakeLLM` / `FakeEmbedder` (no live API calls in tests)
- [ ] `mypy` reports no new errors

---

## Reference

See the full clean-arch rules in
[python-rag-clean-arch SKILL.md](..python-rag-clean-arch/SKILL.md).
