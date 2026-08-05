# Stage 07: Migration Waves And Final Cleanup

Status: completed 2026-08-05.

## Goal

После успешного complexity checkpoint мигрировать остальные authenticated
workflows вертикальными slices и удалить второй постоянный presentation stack.

## Prerequisites

- Stage 06 has an explicit Go decision.
- Shared UI/API conventions are updated from real manual/import experience.
- No unresolved financial/security regression.

## Migration Waves

### Wave A: core financial views

1. [import documents and mapping](import-documents-and-mapping/README.md) —
   completed;
2. accounts and account ledger — completed 2026-07-31;
3. [reports](reports/README.md) — completed 2026-07-31.

### Wave B: reference and rule workflows

1. [properties](properties/README.md) — completed 2026-08-01;
2. [categories](categories/README.md) — completed 2026-08-01;
3. transaction rules — completed 2026-08-02.

### Wave C: context and administration

1. workspaces/members/invitations — completed 2026-08-04;
2. [users, authentication and profile](users/README.md) — completed 2026-08-04;
3. Dashboard — completed 2026-08-05;
4. final authenticated/public SSR consumer audit and cleanup — completed
   2026-08-05.

Before each workflow begins, create a focused child stage with:

- observed behavior inventory;
- API/state boundary;
- geometry baseline;
- security/financial invariants;
- replacement test manifest;
- exact legacy consumer/delete list;
- exit gate.

## Reuse Rule

Manual ledger and import review provide candidates, not mandatory abstractions.
Promote code only when responsibility and contract are stable across real uses.
Do not grow universal CRUD components, generic form generators or feature flags
for unrelated workflows.

## Per-Workflow Exit Gate

- canonical navigation uses React;
- API/application/domain tests cover server authority;
- React tests cover interaction/state/accessibility;
- realistic browser flow passes;
- old routes/presenters/templates/assets/tests are deleted after observation;
- remaining shared legacy code has a named runtime consumer;
- learning docs include newly used TS/React concepts only.

## Final Authenticated SSR Cleanup

After the last authenticated workflow:

- verify that `src/app/web/` and `/_next` have no runtime consumers or source
  files;
- delete remaining authenticated legacy Jinja routes/templates/presenters;
- delete HTMX/Alpine/vendor scripts with no public/auth consumer;
- delete legacy global CSS after its last consumer;
- simplify `scripts/ui_audit.py` to current frontend scenarios;
- keep superseded SSR design documents out of the active repository;
- retain transitional `/app` prefix until its separate routing decision;
- migrate public invitation and development-only browser surfaces to React.

## Final Checks

- full backend quality suite;
- frontend format/lint/type/test/build and critical E2E;
- workspace isolation and financial invariant suite;
- all canonical deep links and redirects;
- security headers/session/CSRF in production-shaped deployment;
- consumer search for Jinja/HTMX/Alpine/`src/app/web`/legacy selectors;
- documentation source-of-truth scan;
- repository contains no unexplained `old`, `legacy` or `next` production copy.

## Final Exit Gate

- React is the only authenticated financial application;
- FastAPI is the only business backend;
- no financial rules were moved to browser authority;
- themes share one semantic token/component system;
- current geometry is preserved or differences are explicitly accepted;
- owner can understand and extend the TypeScript/React code through project
  learning artifacts;
- old presentation code is removed rather than indefinitely maintained.

Completion: public `/` now redirects to the React SPA; invitation preview/
accept and local Telegram dev-link use versioned JSON APIs and React routes.
Jinja templates, templating helpers, HTMX, Alpine, legacy CSS/JS and the Jinja2
dependency were removed. Historical GET redirects remain compatibility
adapters, not a second presentation stack.

Checks: Ruff, ty, full backend (`834 passed, 22 PostgreSQL-only skipped`),
frontend format/lint/styles/OpenAPI/type checks, full Vitest (`92 files, 514
passed`) and production build.
