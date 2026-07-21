# Manual ledger frontend

The feature is split by the question a file answers:

- `api/` — how manual-ledger data is loaded and changed through FastAPI;
- `list/` — how the list, filters, pagination and refreshed rows work;
- `operation/` — how one operation is displayed, created, edited or deleted.

The request flow is:

```text
React route
  -> api/manual-ledger-api.ts
  -> list/manual-ledger-page.tsx
  -> operation components
  -> api/manual-ledger-mutations.ts
  -> authoritative server response
  -> list/manual-ledger-reconciliation.ts
```

State ownership:

- FastAPI owns financial truth and allowed capabilities;
- the route loader owns the fetched list;
- the URL owns search, filters and pagination;
- create/edit components own unsaved form drafts;
- an operation row owns its pending action state;
- list reconciliation keeps a successful response visible until route data is
  revalidated.

Do not add a global store or a generic form/API framework here unless another
feature demonstrates the same stable need.
