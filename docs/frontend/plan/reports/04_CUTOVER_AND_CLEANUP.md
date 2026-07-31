# Slice 04: Reports Cutover And Cleanup

Статус: completed 2026-07-31.

## Outcome

React становится единственным Reports presentation stack. Все canonical entry
points ведут на `/app/reports`, historical `GET /reports` сохраняет query
parameters, а legacy Jinja/HTMX presentation удаляется без удаления shared
reporting application contracts.

## Canonical link migration

Проверить и обновить:

- React `AppShell`;
- dashboard summary;
- authenticated home quick actions;
- onboarding checklist;
- categories index/detail context links;
- properties index;
- legacy base navigation, пока у него остаются runtime consumers;
- chat menu/URL builders;
- workspace permission/return-path tests;
- `scripts/ui_audit.py`;
- test fixtures и documentation links.

Canonical target:

```text
/app/reports
```

## Redirect policy

После полного replacement gate:

```text
GET /reports?... -> /app/reports?...
```

Redirect находится в `src/app/legacy_frontend_redirects.py`, сохраняет query
string и не вызывает Reports service/presenter. Не создавать HTML POST
совместимость: у Reports сейчас нет mutation surface.

## Consumer/delete verification

Выполнить consumer search для:

```text
features/reports/router.py
features/reports/presentation
templates/reports
/reports
report-table
report-period-*
report-filter-*
report-kpi*
HX-Target=report-category-table
ReportsService
ReportsOverview
ReportFilters
summarize_income_expense
```

Удалить:

- legacy Reports router и inclusion из `src/app/main.py`;
- Jinja presenter/ViewModels/templates и HTMX category partial;
- SSR-only URL/sort/template tests;
- Reports-only legacy CSS selectors;
- historical HTML operation из generated OpenAPI schema;
- obsolete Reports scenarios/selectors из legacy UI audit.

Сохранить/refactor:

- `ReportingOverviewReader` и repository aggregate queries;
- Dashboard/Chat/Categories named contracts и tests;
- API/React/browser tests;
- historical GET redirect и test;
- `.report-table`, пока Categories detail остаётся named SSR consumer.

## Replacement test manifest

Backend/API:

- multi-currency, transfers, confirmed-only and Decimal invariants;
- duplicate property/category identity;
- workspace isolation and auth matrix;
- archived filter references;
- no writes during reads;
- bounded results and constant query shape;
- invalid filters/error envelope;
- Dashboard/Chat/Categories consumer regressions;
- redirect query preservation and absence of legacy handler execution.

Frontend:

- generated API freshness and runtime schema;
- format, lint, styles, typecheck, Vitest and production build;
- URL filters/sort/pagination with Back/Forward/reload;
- loading, API error, empty, filtered-empty and review CTA;
- visible currency, `aria-sort`, focus and keyboard/touch behavior.

Browser:

1. empty workspace -> create account;
2. no confirmed data -> Imports/upload;
3. document requiring review -> React review;
4. current month and exact period;
5. account/category/property/currency filters;
6. multi-currency workspace;
7. duplicate property names;
8. category sorting;
9. uncategorized pagination/correction link;
10. viewer readonly flow;
11. historical redirect with query;
12. `1440×1000`, `920×900`, `390×844`, no overflow or console/page/request
    errors.

Quality commands уточняются по фактическим scripts:

```text
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
npm run format:check
npm run lint
npm run styles:check
npm run api:check
npm run typecheck
npm test
npm run build
```

## Measurements

Перед Go записать:

- raw+gzip response size для representative и large workspace;
- SQL query count/shape для 1 и многих accounts/operations/documents;
- uncategorized server maximum и returned DOM row count;
- initial route payload and production chunk size;
- render/interaction baseline на трёх viewport;
- точный список удалённых legacy files/selectors/tests.

## Final exit gate

- canonical navigation и cross-feature links используют React;
- React/API path является единственным Reports presentation contract;
- financial/security policy остаётся server-owned;
- currency никогда не смешивается и всегда видима;
- realistic browser flows и redirect tests прошли;
- legacy router/presenter/templates/HTMX partial отсутствуют;
- consumer search не находит необъяснимый Reports presentation legacy;
- общий reporting application code сохранён только для именованных consumers;
- child plan получает completion record с фактически выполненными checks,
  deviations, cleanup и measurements, после чего детальные completed планы
  сворачиваются по policy активной документации.

## Completion record

Canonical navigation переключена на `/app/reports` в React AppShell, legacy
base navigation, Dashboard, authenticated home, onboarding checklist,
Categories и Properties. Historical `GET /reports` стал query-preserving `307`
redirect и исключён из OpenAPI presentation contract.

Удалены:

- legacy Reports router и его inclusion из `src/app/main.py`;
- Jinja presenter/ViewModels, Reports templates и HTMX category partial;
- SSR-only presenter/template/query tests;
- Reports-only `report-filter-*` и `report-period-*` responsive CSS;
- legacy Reports page из общего browser audit и HTML operation из generated
  OpenAPI types.

Сохранены по consumer search:

- `ReportsService`, `ReportsOverview` и `ReportFilters` для Dashboard и Chat;
- `summarize_income_expense`/`IncomeExpenseSummary` для Categories;
- `.report-table` для SSR Categories detail;
- React/API/repository contracts и historical redirect test.

Measurements:

- representative API fixture: `1573 B` raw, `736 B` gzip;
- synthetic large bounded fixture (100 categories, 50 balances, 25 visible
  uncategorized rows): `50988 B` raw, `1088 B` gzip;
- production read shape: `10` constant SQL queries, включая count + bounded
  page; число запросов не зависит от числа accounts/operations/documents;
- API и rendered DOM maximum uncategorized page size: `25`; default UI page
  size — `10` строк;
- Reports route chunk: `24.86 kB`, gzip `7.30 kB`; CSS: `5.14 kB`, gzip
  `1.18 kB` до финального cutover build.

Проверены backend Reports/API/redirect и Dashboard/Chat/Categories consumers,
React Reports/AppShell, OpenAPI freshness, production build и browser layouts
на `1440×1000`, `920×900`, `390×844`. Intentional deviation: shared legacy
reporting service и `.report-table` не удалены из-за именованных runtime
consumers, перечисленных выше.
