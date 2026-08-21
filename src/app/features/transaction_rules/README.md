# Transaction rules runtime boundary

Transaction rules are workspace-scoped suggestions for imported rows. They may
prefill operation type, category, property or description, but never bypass
ledger validation or user-review policy.

```text
API/chat -> application service -> domain matcher -> repository -> model
```

- Repository queries always include `workspace_id`.
- Write commands use optimistic version and stable conflict errors.
- Matching is deterministic; unsafe or ambiguous rows remain reviewable.
- Browser capabilities come from the API, not client-side role inference.
- Import objects from their defining modules; do not add package facades.

Relevant tests cover workspace isolation, matcher behavior, lifecycle conflicts
and API/React contracts.
