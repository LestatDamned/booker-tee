# React Frontend Implementation Plan

Статус: active execution index.

Этот каталог содержит только текущую миграцию. Детальные completed stage plans
удалены; их результат зафиксирован ниже, а implementation history остаётся в
Git и коде.

## Current position

```text
Stages 0–6 completed
Stage 7 active
Imports completed
Accounts and account ledger completed
Reports completed; canonical UI is React
Properties, Categories and Transaction Rules completed; canonical UI is React
```

## Completed outcomes

| Stage | Outcome                                                                     |
| ----- | --------------------------------------------------------------------------- |
| 0     | React SPA, versioned API, CSS/themes и learning decisions приняты в ADR     |
| 1     | React build и safe session/API foundation работают                          |
| 2     | Semantic tokens, themes и shared UI foundation проверены                    |
| 3–5   | Manual Ledger полностью работает в React; legacy mutation UI удалён         |
| 6     | Import Review полностью работает в React; legacy review presentation удалён |

Подробные контракты завершённых features находятся рядом с кодом:

- `frontend/app/features/manual-ledger/README.md`;
- `frontend/app/features/import-review/README.md`;
- `frontend/app/features/accounts/README.md`;
- `frontend/app/features/transaction-rules/README.md`;
- server application/domain tests.

## Current stage

[`STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md`](STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md)
мигрирует остальные authenticated workflows и удаляет второй presentation
stack.

Child stages:

- [`Import documents and mapping`](import-documents-and-mapping/README.md) —
  completed;
- Accounts and account ledger — completed 2026-07-31;
- [`Reports`](reports/README.md) — completed 2026-07-31;
- [`Properties`](properties/README.md) — completed 2026-08-01;
- [`Categories`](categories/README.md) — completed 2026-08-01;
- Transaction Rules — completed 2026-08-02.
- Workspaces — completed 2026-08-04.
- [`Users and authentication`](users/README.md) — active; Slice 1 completed,
  increments 2.0–2.2 completed; next increment is 2.3 Session hardening and
  management.

### Workspaces completion record

Completed: 2026-08-04

Implemented: canonical React directory/settings with create/switch, members,
invitations, ownership, leave, deactivate/restore and versioned JSON API;
server-owned capabilities, idempotency, optimistic concurrency and workspace
boundary reloads. Public invitation preview/accept remains a minimal named SSR
bridge.

Cleanup performed: historical GET now query-preserving redirects to React;
authenticated legacy form routes, presenter/ViewModels, index/card templates,
workspace-only global CSS and generated HTML operations were removed. AppShell
and remaining SSR entry points use the canonical route.

Checks run: Ruff, ty, full backend (`792 passed, 15 PostgreSQL-only skipped`),
full frontend (`79 files, 477 passed`) with format/lint/styles/OpenAPI/type/build,
and six Mocha canonical/historical browser checks at 1440/920/390.

### Transaction Rules completion record

Completed: 2026-08-02

Implemented: workspace-scoped versioned JSON directory/create/edit/seed,
lifecycle and safe-delete API; canonical responsive React directory; URL-owned
filters/pagination; right-side create panel; inline row editor; server-owned
capabilities, concurrency and Import Review semantics.

Checks run: Slice 6 full backend (`716 passed, 6 skipped`), focused Import
Review/unknown mapping/Chat regressions (`79 passed`), generated API/adapter
regression (`137 passed`), latest frontend suite (`391 passed`), frontend
format/lint/styles/typecheck/build and responsive Transaction Rules browser
audits. The replacement browser flow passed in Mocha and Latte at
1440/920/390 before final design-only stabilization.

Intentional deviations: dormant legacy fields outside the accepted first
React form remain server-preserved rather than silently overwritten. The
temporary `/app` prefix remains until the global Stage 7 routing decision.

Cleanup performed: canonical navigation and cross-feature links moved to
React; legacy router, presenter, templates, SSR-only adapters/tests,
rule-specific global hooks and legacy HTML OpenAPI operations removed. The
detailed child migration plan was deleted after this completion record and the
durable feature contracts were moved next to code.

Measurements/risks: rules affect only future matching or an explicit Apply
rules action and never confirm ledger records. Existing suggestions are not
silently rewritten; hard delete remains limited to disabled, directly
unreferenced rules with restrictive database provenance protection.

### Categories completion record

Completed: 2026-08-01

Implemented: workspace-scoped Categories API; React directory/detail,
create/edit, financial drill-down, archive/restore/delete and direct row
actions; query-preserving historical GET redirects; canonical navigation.

Cleanup performed: legacy Categories router, presenter/ViewModels, two Jinja
templates, 15 replacement-only SSR tests, category-only global CSS/JS hooks and
legacy HTML OpenAPI operations removed. Browser fixture now uses React/API.

Checks run: Ruff, ty, full backend (`683 passed, 1 skipped`), frontend full
check (`357 passed`) and production build; Mocha/Latte realistic audit for
directory/detail/redirect at 1440/920/390 (`9/9` pages per theme).

Measurements/risks: directory `19.59 kB` (`6.81 kB` gzip), detail `27.87 kB`
(`8.91 kB` gzip); Transaction Rules subsequently completed without removing
its category domain/API consumers.

### Properties completion record

Completed: 2026-08-01

Implemented: versioned workspace-scoped Properties API; React directory,
create/edit/archive/restore and Reports links; query-preserving historical GET
redirect; canonical navigation.

Checks run: Ruff, ty, full backend suite (`661 passed, 1 PostgreSQL-only
skipped`) plus 261 focused regressions, frontend format/lint/styles/OpenAPI/
typecheck, 305 React tests, production build, Mocha/Latte browser audit for
canonical and redirect routes at 1440/920/390.

Cleanup performed: legacy router/presenter/template/SSR tests, property-only
global CSS/JS hooks and legacy generated OpenAPI operations removed.

Measurements/risks: Properties route `24.94 kB` (`7.94 kB` gzip), CSS
`1.82 kB` (`0.69 kB` gzip); dormant database enum label `inactive` remains by
accepted D1 policy, while runtime exposes only `active | archived`.

### Reports completion record

Completed: 2026-07-31

Implemented:

- currency-safe Reports API and React overview, breakdowns and bounded
  uncategorized operations;
- URL filters, sorting, pagination, responsive records and server-owned
  correction capabilities;
- query-preserving historical GET redirect.

Cleanup performed:

- removed legacy Reports router, Jinja presenter/ViewModels/templates, HTMX
  partial and replacement-only tests;
- switched canonical cross-feature links to React;
- removed Reports-only legacy CSS and HTML OpenAPI operation.

Named shared consumers remain: Dashboard/Chat use the legacy-named reporting
read service, Categories uses its pure summary policy, and Categories detail
uses `.report-table`.

### Accounts completion record

Completed: 2026-07-31

Implemented:

- React account directory, detail ledger, settings, lifecycle и imported
  operation correction;
- versioned Accounts API с workspace/capability/concurrency contracts;
- query-preserving historical GET redirects.

Cleanup performed:

- удалены legacy Accounts router, Jinja presenter/ViewModels/templates и их
  replacement-only tests;
- удалён account-specific legacy CSS;
- canonical dashboard/report links переключены в React;
- HTML account operation удалена из generated OpenAPI types.

Checks run:

- relevant backend Accounts/redirect/users tests;
- frontend format/lint/styles/API/type/tests/build;
- Accounts browser audit на desktop/tablet/mobile.

Intentional deviations: none.

Measurements/risks: financial/domain actors сохранены без переписывания;
временный `/app` prefix остаётся до общего Stage 7 routing cutover.

## Status rules

- `planned` — scope принят, implementation не начат;
- `next` — ближайший stage/workflow;
- `active` — production implementation идёт;
- `blocked` — exit gate требует внешнего решения;
- `completed` — outcome достигнут, cleanup и checks записаны.

Одновременно active только один global stage. Child slices могут иметь свой
статус внутри active stage.

## Execution rules

1. Workflow делится на пользовательские vertical slices.
2. Slice проходит `application/API -> state -> UI -> tests`.
3. Domain/application не переписываются ради React.
4. Legacy работает до replacement gate, но не получает новые abstractions.
5. Cleanup входит в slice.
6. Server остаётся владельцем financial/security policy.
7. Completed детальные планы удаляются после краткой записи результата здесь.

## Completion record

При завершении текущего stage оставить короткий record:

```text
Completed: YYYY-MM-DD
Implemented:
Checks run:
Intentional deviations:
Cleanup performed:
Measurements/risks:
```

Не превращать record в журнал каждого commit.
