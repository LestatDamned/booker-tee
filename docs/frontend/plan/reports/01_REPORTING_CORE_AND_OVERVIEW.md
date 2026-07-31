# Slice 01: Currency-Safe Reporting Core And Overview

Статус: completed 2026-07-31.

## Outcome

Пользователь открывает `/app/reports`, выбирает период, currency и точные
фильтры, видит финансово корректные KPI одной валюты и balances с явной датой
snapshot. Slice создаёт production reporting read model и versioned JSON API;
он не оборачивает текущий unbounded `ReportsService.build_overview()`.

## Application/repository

Добавить `ReportingOverviewReader` и focused aggregate repository queries.

Reader:

- принимает workspace id и normalized `ReportFilters` с explicit currency;
- проверяет reversed range и workspace ownership выбранных references;
- получает summary, account balances, filter options и optional review CTA;
- не seed-ит reference data и не открывает transaction для записи;
- возвращает application DTO, не ORM graph.

Repository:

- агрегирует только confirmed entries/operations;
- исключает `affects_profit=false` из profit aggregates;
- фильтрует summary по `MoneyEntry.currency`;
- получает balances одним aggregate query, включая initial balance;
- возвращает bounded filter projections и один review document;
- во всех запросах имеет явный workspace predicate.

На этом slice category/property rows могут уже входить в response shape, но их
полный UI и sorting gate принадлежат Slice 02. Uncategorized — только count или
пустая bounded page до Slice 03.

## JSON API

Добавить:

```text
GET /api/v1/reports
```

Initial response:

```text
workspace
appliedFilters
filterOptions
summary { currency, income, expense, profit }
accountBalances[] { accountId, name, currency, balance, isActive }
balanceAsOf
nextReviewDocument?
categoryRows[]
propertyRows[]
uncategorized { items, page, pageSize, total }
```

Money fields — decimal strings. Dates — ISO. API возвращает stable facts и
reason codes, но не labels, href или tones.

Auth minimum: authenticated active workspace member with read access. Viewer,
analyst/uploader и manager видят одинаковую финансовую истину; capabilities
различают только доступные follow-up actions.

## Frontend state/UI

- Route `/app/reports`, lazy/route-level feature boundary по существующему
  React Router pattern.
- Loader парсит URL, вызывает generated/focused client и runtime schema.
- Default currency видима с первого render.
- Period navigation: previous, next, current month, all time.
- Exact filter draft: dates, currency, account, category, property.
- Apply/Reset пишут normalized state в URL.
- KPI использует `MoneyValue`; account balances явно подписаны `balanceAsOf`.
- Empty workspace, empty report, review-needed, filtered-empty и request error —
  отдельные states с безопасным recovery path.
- AppShell link меняется только после replacement gate Slice 04, чтобы не
  создавать canonical broken route во время partial implementation.

## Tests

Backend:

- multi-currency operations не смешиваются;
- default currency normalization;
- transfer excluded from KPI, included in account balances;
- confirmed-only calculations;
- date/account/category/property filters;
- reversed date range rejected;
- foreign-workspace filter reference rejected/not exposed;
- archived selected references представлены корректно;
- read не seed/flush/commit;
- balance aggregate query count не зависит от account count;
- Dashboard/Chat currency regression tests.

API:

- unauthenticated and inactive-member behavior;
- viewer/analyst/uploader/manager read matrix;
- decimal-string and UUID/date schema;
- invalid query error envelope;
- empty workspace contract;
- generated OpenAPI and runtime schema agreement.

Frontend:

- loader success/schema/network error;
- URL normalization and Apply/Reset;
- month navigation preserves compatible filters;
- Back/Forward and reload restoration;
- visible currency and balance date semantics;
- empty/review/error states;
- keyboard and accessible names for period/filter controls;
- desktop/tablet/mobile overview geometry.

## Replacement gate

Slice может опубликовать `/app/reports`, но legacy `/reports` и его navigation
остаются до завершения breakdowns и uncategorized replacement. Никакой Jinja
код на этом этапе не удаляется, кроме явно мёртвого после consumer search.

## Exit gate

- production API не использует текущую Python in-memory aggregation path;
- currency, transfer и confirmed-only invariants доказаны tests;
- query shape constant относительно accounts/operations;
- overview page доступна по direct deep link и корректно восстанавливает URL;
- UI однозначно показывает currency и balance snapshot semantics;
- Dashboard/Chat не подписывают mixed result default currency.

## Completion record

Completed: 2026-07-31

Implemented:

- workspace-scoped `ReportingOverviewReader` и aggregate
  `ReportsRepository` без in-memory aggregation;
- `GET /api/v1/reports` с explicit currency, decimal-string money, filter
  ownership validation и generated TypeScript contract;
- `/app/reports` с URL-периодом, точными фильтрами, KPI и balance snapshot;
- currency forwarding для legacy Reports, Dashboard и chat consumers.

Checks run:

- Ruff, ty и focused backend/API pytest;
- frontend format, lint, styles, API drift, typecheck и focused Reports tests;
- production build;
- authenticated realistic browser audit на `1440×1000`, `920×900` и
  `390×844` без horizontal overflow, console/page/network errors.

Intentional deviations:

- category/property aggregates уже входят в API, но их UI остаётся Slice 02;
- uncategorized page/count не добавлены в initial response до Slice 03;
- canonical `/reports` и AppShell link остаются legacy до Slice 04.

Cleanup performed: legacy presentation не удалялась до replacement gate.

Measurements/risks: Reports route chunk — `12.14 kB`, gzip `4.22 kB`;
repository read shape имеет фиксированное число aggregate/projection queries.
