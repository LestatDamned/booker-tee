# Manual operation commands

The feature is split by the question a file answers:

- `api/` — how source-specific manual commands use FastAPI;
- `list/` — the reused canonical Operations workbench, filters and pagination;
- `operation/` — how one operation is displayed, created, edited or deleted.

The request flow is:

```text
React /operations route
  -> api/v1/operations read contract
  -> list/manual-ledger-page.tsx
  -> operation components
  -> api/manual-ledger-mutations.ts
  -> authoritative server response
  -> list/manual-ledger-reconciliation.ts
```

State ownership:

- FastAPI owns financial truth and allowed capabilities;
- the Operations route loader owns the fetched list;
- the URL owns search, filters and pagination;
- create/edit components own unsaved form drafts;
- an operation row owns its pending action state;
- list reconciliation keeps a successful response visible until route data is
  revalidated.

Do not add a global store or a generic form/API framework here unless another
feature demonstrates the same stable need.

Старого manual-only list route и read API больше нет. Workbench получает только
`OperationsListApiResponse`; manual endpoints сохранены исключительно для
create/edit/lifecycle/delete и повторно проверяют source и workspace на backend.
