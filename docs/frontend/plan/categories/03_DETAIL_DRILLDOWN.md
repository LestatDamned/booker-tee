# Slice 03: Detail and Reports drill-down

Статус: `completed 2026-08-01`.

## Outcome

User opens `/app/categories/:categoryId` from directory or Reports and receives
currency-safe summary, paginated confirmed operations, linked rules preview and
correct back context.

## Server

- `CategoryDetailReader` and `GET /api/v1/categories/{id}`;
- ISO date/currency/income-expense validation;
- reuse pure Reports summary policy and Decimal calculations;
- filter confirmed operations by workspace/category/period/currency/type;
- bounded pagination and mapped operation DTOs, no ORM leakage;
- bounded rules preview with total/active counts;
- 404 without cross-workspace existence leak;
- tests: transfer exclusion, profit arithmetic, currency separation, ordering,
  pagination and archived/system detail.

## React

- detail loader/request states and safe URL parser;
- local `return_to` accepts only `/app/reports...`;
- compact `MoneyValue` summary and filter context;
- `ReadOnlyFinancialRow` + `WorkbenchPagination` for display-only operations;
- linked rules preview and temporary canonical historical Rules link;
- update Reports category drill-down to `/app/categories/:id` only after route is
  replacement-ready; legacy detail remains available until cutover.

## Exit gate

- direct detail defaults to workspace currency;
- Reports period/currency/back context survives refresh;
- transfer never changes summary;
- large history does not render unbounded rows;
- mobile has no horizontal overflow.

## Completion record

Implemented:

- `CategoryDetailReader` и `GET /api/v1/categories/{id}` собирают только
  workspace-scoped DTO и возвращают одинаковый `404` для отсутствующей и чужой
  категории;
- period, currency, type и bounded pagination валидируются на API boundary;
  summary переиспользует Reports policy с явной валютой и исключает операции,
  которые не влияют на прибыль;
- operation page считается по уникальным операциям, поэтому transfer с двумя
  проводками не искажает `LIMIT/OFFSET`; правила ограничены preview из пяти
  записей с authoritative total/active counts;
- `/app/categories/:categoryId` использует parallel session/detail loader,
  безопасный Reports `return_to`, UI Foundation summary, filters, read-only
  records, pagination, empty/request states и historical Rules links;
- directory identity и Reports category breakdown переключены на React detail
  после покрытия route/API тестами.

Checks:

- focused backend detail/API tests, Ruff и ty — passed;
- full backend regression — `682 passed, 1 PostgreSQL-only skipped`;
- focused и full React suites — `340 passed`; OpenAPI drift, Prettier, ESLint,
  style contract, TypeScript и production build — passed;
- realistic Mocha/Latte browser audit на 1440/920/390 — 6/6 passed, horizontal
  overflow и browser errors отсутствуют.

Measurements после Slice 03.1: category detail main chunk `12.24 kB`
(`4.46 kB` gzip), feature CSS `2.80 kB` (`0.79 kB` gzip), общий
`ReadOnlyFinancialRow` — `1.10 kB` JS (`0.49 kB` gzip) и `1.74 kB` CSS
(`0.68 kB` gzip).

Intentional deferrals: edit принадлежит Slice 04; lifecycle/delete — Slice 05;
historical Categories cutover и legacy cleanup — Slice 06; Rules preview
остаётся historical до Transaction Rules migration.

## Slice 03.1: read-only operations alignment

Статус: `completed 2026-08-01`.

После повторного UI-аудита display-only операции отделены от интерактивных
рабочих строк:

- `WorkbenchRow` сохраняет контракт выбора, действий и раскрытия и не получает
  read-only режим;
- общий `ReadOnlyFinancialRow` используется в Category Detail, Import Document
  Detail и Import Mapping preview;
- один semantic list адаптируется CSS-геометрией без дублирования desktop/mobile
  DOM;
- detail toolbar переиспользует `WorkbenchSearch`, `AppliedFilterSummary` и
  `WorkbenchPagination`, включая page-size control;
- поиск по описанию фильтрует только список/count операций, сохраняет финансовый
  и Reports context и не меняет authoritative summary категории.

Exit gate: read-only строки не кликабельны и не входят в tab order; search,
filters, pagination и page size сохраняют URL-state; import problem rows
сохраняют видимые issues и danger rail.

Checks Slice 03.1: focused React `30 passed`, full React `340 passed`, focused
backend `17 passed`, full backend `682 passed, 1 PostgreSQL-only skipped`;
Prettier, ESLint, style contract, OpenAPI drift, TypeScript, Ruff, ty и
production build — passed.
