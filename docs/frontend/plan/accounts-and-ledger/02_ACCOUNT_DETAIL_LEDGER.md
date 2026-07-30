# Slice 02: Account Detail And Ledger

Статус: completed.

## Outcome

Пользователь открывает `/app/accounts/:accountId`, видит authoritative balance,
фильтрует paginated movements и переходит в правильный source workflow.

## API/application

Добавить:

```text
GET /api/v1/accounts/{account_id}
```

Query parameters:

```text
date_from
date_to
source
type
status
category_id
property_id
search
page
per_page
```

Application detail projection содержит:

- account facts/current mutation token;
- authoritative current balance и initial balance;
- matched movement count и pagination;
- account-relative movements с Decimal amount;
- operation identity/version/date/type/status/source/description;
- category/property и transfer account references;
- typed source target kind/ids;
- filter options и page/movement capabilities.

Current balance всегда считается по confirmed entries и не меняется от list
filters. Read не seed-ит categories, не делает commit и не исправляет status.
Inactive persisted references остаются representable.

## Frontend state/UI

- Route: `/app/accounts/:accountId`.
- Все filters и pagination принадлежат URL; изменение filter сбрасывает page.
- Default status — `confirmed`, как в существующем workflow.
- Header показывает balance, initial balance, currency, type и active state.
- Movement row использует shared money/status/workbench primitives.
- Manual source ведет в `/app/ledger/manual?operation_id=...`.
- Imported source ведет к canonical React Import Review/document context.
- Transfer route показывается из server facts и имеет текст «не влияет на
  прибыль»; frontend не вычисляет counterparty по entries.
- System operation readonly.
- No results, unavailable, forbidden и request error имеют разные states.
- Optional `operation_id` query/anchor вводится только вместе с test на deep
  link, focus и Back/Forward.

## Tests

Backend:

- account/workspace isolation;
- filter parsing, deterministic ordering и pagination bounds;
- current balance не зависит от filters;
- confirmed/non-confirmed entry behavior;
- transfer account-relative amount и route facts;
- source target/capability matrix;
- inactive category/property projection;
- detail read не делает commit/seed.

Frontend:

- URL round-trip для каждого filter и pagination;
- invalid query normalization;
- loading/error/empty/populated states;
- positive/negative/zero and transfer rendering;
- manual/import/system source links;
- filter reset и Back/Forward;
- keyboard/focus/accessibility;
- responsive header, filter panel и movement rows.

Browser:

- empty ledger;
- confirmed income/expense;
- transfer между двумя accounts;
- imported and manual source links;
- filtered result and pagination;
- reload/deep link на desktop/tablet/mobile.

## Replacement/delete

После gate:

- historical detail GET становится query-preserving redirect;
- legacy detail page presenter и read-only movement templates удаляются, если
  mutation slices больше их не используют;
- historical settings/correction mutations остаются только до своих gates.

## Exit gate

- list и cross-feature links открывают React detail;
- authoritative balance/filters/pagination доказаны server tests;
- source links ведут в существующие React workflows;
- historical detail GET только redirect;
- browser flow не имеет overflow, console/page/request errors.

## Completion record

Completed: 2026-07-30.

Implemented:

- workspace-scoped `GET /api/v1/accounts/{account_id}` с tolerant URL filters,
  authoritative balance, account-relative movements и typed source targets;
- React route `/app/accounts/:accountId` в общем workbench-паттерне Manual
  Operations: header balance, search/filter toolbar, movement rows и pagination;
- manual/import/system source navigation и server-owned transfer route;
- list, shell и historical detail GET переключены на canonical React route.

Checks run:

- focused backend API, redirect, React component and type checks;
- realistic Playwright audit на `1440x1000`, `920x900`, `390x844`.

Intentional deviations:

- mutation token и management capabilities остаются в Slice 03, потому что
  Slice 02 не меняет account settings;
- source target передаёт typed ids/facts, а browser URL строится React adapter.

Cleanup performed:

- historical `/accounts/{account_id}` стал query-preserving redirect;
- list и shell больше не ведут на SSR detail.

Measurements/risks:

- browser audit: 3/3 pages passed, horizontal overflow `0`, без console/page/
  request errors;
- legacy imported-operation correction partials остаются до Slice 04.
