# Slice 03: Detail and Reports drill-down

Статус: `planned`.

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
- `ResponsiveRecordCollection` + `WorkbenchPagination` for operations;
- linked rules preview and temporary canonical historical Rules link;
- update Reports category drill-down to `/app/categories/:id` only after route is
  replacement-ready; legacy detail remains available until cutover.

## Exit gate

- direct detail defaults to workspace currency;
- Reports period/currency/back context survives refresh;
- transfer never changes summary;
- large history does not render unbounded rows;
- mobile has no horizontal overflow.

