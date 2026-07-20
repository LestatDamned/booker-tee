# Stage 03: Manual Ledger Read Path

Status: completed.

## Goal

Провести первый financial read workflow через полный target flow без mutations:

```text
React route -> /api/v1 -> application query -> repository
```

## User-Visible Outcome

Пользователь открывает React manual ledger, видит реальные operations, total,
filters, pagination, readonly capabilities и устойчивые URL/deep-link states.

## Prerequisites

- Stage 02 completed.
- [`MANUAL_LEDGER_BASELINE.md`](../../design/MANUAL_LEDGER_BASELINE.md)
- current SSR и Frontend Next доступны для behavior comparison.

## Scope

### API

- manual-ledger list response schema;
- tolerant query parsing for period, search, type, status, account, category,
  property and page;
- decimal-string money and explicit currency/financial semantics;
- per-row capabilities and readonly reasons;
- pagination and total contract;
- workspace isolation and predictable `400/401/403/422` errors.

### React

- route-owned URL state;
- list loader/request states;
- filters with Apply/Reset and shareable URL;
- `ManualOperationRow` composed from shared `WorkbenchRow` primitives;
- income/expense/transfer and lifecycle presentation;
- loading, empty, error, readonly and populated states;
- stable entity target/deep link without automatic scroll on local rerender.

## Ordered Slices

1. Compare both SSR implementations and record the exact read contract.
2. Add backend response/query schemas and API contract tests.
3. Generate DTO and create explicit frontend mapping.
4. Render one realistic row with correct money semantics.
5. Add list states and pagination.
6. Add filters and canonical URL serialization.
7. Add readonly/capability behavior.
8. Run geometry/performance comparison on realistic data.

## State Ownership

| State | Owner |
| --- | --- |
| filter values after Apply | URL / React Router |
| fetched rows and total | server state at route/feature boundary |
| filter disclosure open/closed | local component state |
| row capabilities | API response |
| money semantics | API response |
| formatted visual value | focused frontend formatter |

## Learning Outcomes

- route loader/request против обычного Python function call;
- URL search params как serializable state;
- DTO mapping как frontend adapter;
- `.map()` rendering и необходимость stable `key`;
- props down / events up;
- discriminated union для loading/success/empty/error;
- controlled filter form против applied URL state.

## Checks

- backend schema, filter and workspace-isolation tests;
- transfer never rendered as income/expense from amount sign;
- frontend mapping and formatter unit tests;
- route tests for filters/reset/pagination/deep links;
- realistic browser comparison desktop/920/mobile;
- readonly actions are absent or explained from capabilities;
- no extra per-row request or query explosion;
- existing SSR behavior remains unchanged.

## Out Of Scope

- create/edit/cancel/restore/delete;
- optimistic mutation updates;
- cutover of canonical `/ledger/manual`;
- deletion of either SSR manual implementation;
- abstraction of account-ledger row before real use.

## Exit Gate

- React read path matches required manual baseline;
- API contains no Jinja ViewModel or HTML fragment;
- filters and pagination survive refresh and copied URL;
- geometry and accessibility pass realistic audit;
- owner can trace query params -> API -> mapping -> component tree.

Next: [`Stage 04`](STAGE_04_MANUAL_LEDGER_MUTATIONS.md).

## Completion Record

Completed: 2026-07-20

Implemented: workspace-scoped JSON list API, decimal-string financial
semantics, capability and reference-option contracts, generated DTO, explicit
UI mapper, responsive React list, request/empty/readonly states, URL-owned
filters, pagination and stable operation deep links.

Checks run: Ruff format/lint, ty, API/presentation pytest (28 passed), full
frontend check including TypeScript, ESLint, CSS rules, 30 Vitest tests and
production build, plus realistic Playwright audit at 1440, 920 and 390 px.

Intentional deviations: no mutation controls are rendered during the read-only
stage; capabilities already cross the API boundary and become actionable in
Stage 04.

Cleanup performed: React reset and pagination remain inside the `/app` route;
the route loader was separated into an imported module so React Router's
production route splitting includes it safely.

Learning notes updated: OpenAPI/Zod boundary, DTO-to-UI mapping, controlled
filter draft versus applied URL state, and production route-splitting boundary.
