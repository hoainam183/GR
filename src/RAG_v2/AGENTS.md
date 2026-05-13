# AGENTS.md — RAG_v2 Coding Workflow

## Required Module Documentation Workflow

Before editing code in any module:

1. Identify every module directory directly affected by the change.
2. Read that module's `MODULE.md` before coding or fixing bugs.
3. If the change touches multiple modules, read each affected module's `MODULE.md`.
4. If an affected module does not have `MODULE.md`, read `PROJECT_MEMORY.md` and nearby source files to reconstruct the context, then mention the missing module document in the final response.

After implementation:

1. Run the most relevant test or check for the changed code.
2. Only after the test/check succeeds, update the `MODULE.md` files for modules whose code changed.
3. Update `PROJECT_MEMORY.md` only when the change affects architecture, public APIs, cross-module contracts, data flow, or system-level behavior.

## Documentation Scope

- `MODULE.md` is the source of truth for module-level behavior, local patterns, public classes/functions, and module-specific test notes.
- `PROJECT_MEMORY.md` is the source of truth for project-level architecture, major workflows, shared contracts, and cross-module behavior.
- Keep documentation updates concise and focused on behavior that future coding agents need to know.
