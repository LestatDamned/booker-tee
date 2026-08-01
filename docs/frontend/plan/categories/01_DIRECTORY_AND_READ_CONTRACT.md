# Slice 01: Directory and read contract

Статус: `completed 2026-08-01`.

## Outcome

Authenticated user открывает `/app/categories`, видит authoritative directory,
ищет category и переключает Active/Archive/System. SSR остаётся canonical до
Slice 06.

## Server

- application directory DTO/service without Jinja presenter dependency;
- `GET /api/v1/categories` with workspace read permission;
- summaries/counts/capabilities/system facts and kind option copy;
- all queries workspace-scoped;
- characterize write-on-read seeding and keep it explicit;
- full operation/rule counts suitable for usage and lifecycle facts;
- API auth/403/schema/isolation tests and OpenAPI regeneration.

## React

- route loader and recoverable `RequestState`;
- `AppShell -> PageFrame -> WorkbenchSurface`;
- `WorkbenchSearch`, `SelectionTabs`, URL normalization;
- responsive table/mobile list, concise open action, notes/kind/status/usage;
- system/read-only explanation, empty/no-results states;
- no mutation controls until Slice 02.

## Exit gate

- refresh/back/forward preserve applied search/view;
- invalid/legacy `view=all` normalization follows D1;
- no browser-derived permissions/system policy/counts;
- keyboard/reader names and 390px layout pass;
- SSR unchanged and still operational.

## Completion record

Implemented:

- `CategoryDirectoryService` и immutable application DTOs отделены от Jinja
  presenter;
- `GET /api/v1/categories` возвращает workspace-scoped category facts,
  confirmed operation counts, total/active rule counts, kind option copy,
  read-only/capability facts и accepted active-rule archive blocker;
- `/app/categories` загружает session/API параллельно, хранит `view/search` в
  URL и нормализует historical `view=all` в Active;
- directory использует существующие `WorkbenchSurface`, search, tabs,
  responsive records, Tag, StatusLabel, notices и empty states;
- category identity временно ведёт в operational SSR detail до Slice 03/06;
  AppShell navigation остаётся SSR-canonical до replacement gate;
- UI audit знает отдельный `react-categories` route.

Checks:

- Ruff format/check и `ty check` — passed;
- полный backend suite — `667 passed, 1 PostgreSQL-only skipped`;
- frontend format/lint/styles/OpenAPI/typecheck — passed;
- полный frontend suite — `318 passed`;
- production build — passed;
- authenticated browser audit в Mocha и Latte на 1440/920/390 — 6/6 passed,
  horizontal overflow и browser errors отсутствуют.

Measurements: route main chunk `8.49 kB` (`3.28 kB` gzip), feature CSS
`1.50 kB` (`0.57 kB` gzip).

Intentional deferrals: create, detail React route и mutations принадлежат
Slices 02–05; canonical routing/cleanup принадлежит Slice 06.
