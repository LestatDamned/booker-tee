# Slice 01 — Directory and read contract

Статус: completed 2026-08-01.

## User outcome

Authenticated participant открывает `/app/properties`, видит workspace-scoped
directory, понятные lifecycle views, search, empty/read-only/error states и
может перейти в Reports. SSR `/properties` пока остаётся canonical.

## Application/API

Добавить узкий Property directory read actor; не отдавать ORM model напрямую и
не переиспользовать Jinja ViewModel.

Предлагаемый endpoint:

```text
GET /api/v1/properties
```

Response содержит:

- `items[]`: `id`, `name`, `shortName`, `address`, accepted lifecycle status,
  `archivedAt`, `updatedAt`;
- row capabilities: `canUpdate`, `canArchive`, `canRestore` и optional stable
  blocking reason;
- directory capabilities: `canCreate`, read-only reason;
- optional server-owned lifecycle impact facts, если они нужны принятому D2.

API использует `get_api_request_context`, workspace id только из session и
stable `401/403` errors. Search/status view можно применять к небольшому
authoritative snapshot в client, как в Accounts; если measurement покажет
большие per-workspace lists, filtering/pagination переносится на server до
cutover, а не после performance regression.

## React state

- route loader параллельно загружает session и directory;
- runtime schema валидирует critical network boundary;
- URL хранит normalized search и lifecycle view;
- loader snapshot/server response — entities и capabilities;
- local state — disclosure, pending и transient focused row;
- invalid URL values нормализуются без выдумывания entity/status.

## UI

Собрать directory по структуре из `UX_AUDIT.md`: shared workbench, search,
status tabs, responsive collection, empty/no-results/read-only states.
Property identity остаётся name; short name и address получают явную визуальную
роль. Не показывать money/ROI и не создавать shared PropertyCard.

До следующих slices create/edit/lifecycle controls могут отсутствовать даже
при capability; нельзя публиковать кнопки-заглушки.

## Tests

- repository/application: workspace isolation, stable ordering, duplicate names
  с разными UUID, status mapping;
- API: 401, unreadable workspace 403, capabilities per role, no foreign rows,
  response casing/OpenAPI;
- frontend API: runtime validation, network/401/error;
- route: session/directory loading and recovery paths;
- page: URL search/status, counts, empty/no-results/read-only, desktop/mobile
  semantic parity, keyboard navigation;
- browser smoke 1440/920/390 in Mocha and Latte.

## Exit gate

- D1 представлен в API/UI без silent coercion;
- no mutation controls or endpoints are required for this slice;
- SSR remains untouched and canonical;
- other active Property reference consumers pass relevant tests.

## Completion record

Implemented:

- migration `20260801_0019` нормализует dormant `inactive` в `archived`;
- workspace-scoped `PropertyDirectoryService` и `GET /api/v1/properties` с
  server-owned row/directory capabilities;
- typed runtime-validated React loader и `/app/properties` directory с URL
  search/lifecycle view, responsive table/cards, empty/read-only/error states и
  property-scoped переходом в Reports;
- SSR `/properties` сохранён canonical, mutation controls не публиковались.

Checks:

- backend Properties/API/OpenAPI и связанные Reports/ledger tests;
- Ruff, ty, frontend format/lint/styles/API/type tests и production build;
- browser audit Mocha и Latte на 1440/920/390 без overflow/browser errors.

Known follow-up: create/edit/lifecycle и canonical cutover выполняются только в
Slices 02–05.
