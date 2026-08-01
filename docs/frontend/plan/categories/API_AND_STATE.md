# Categories API and state boundary

Статус: accepted contract; D1–D5 приняты 2026-08-01, Slice 01 read boundary
реализован.

## Application boundary

Не отдавать ORM `Category`, `Operation` и `TransactionRule` прямо в API.
Добавить focused application readers/commands внутри Categories:

```text
CategoryDirectoryService
  read(workspace_id, can_write)
  create(workspace_id, command)
  update(workspace_id, category_id, command)
  archive/restore/delete(... expected_updated_at)

CategoryDetailReader
  read(workspace_id, category_id, filters, pagination)
```

Reader собирает DTO из workspace-scoped repositories. Pure reporting summary
policy переиспользуется; Jinja presenter не становится API mapper. Router
занимается HTTP schemas/errors/dependencies, а не financial calculations.

## Proposed endpoints

| Method | Endpoint | Outcome |
| --- | --- | --- |
| `GET` | `/api/v1/categories` | all category summaries + directory capabilities/kind options |
| `POST` | `/api/v1/categories` | create custom category |
| `GET` | `/api/v1/categories/{id}` | detail, summary, paginated operations, linked-rule preview |
| `PUT` | `/api/v1/categories/{id}` | update custom name/kind/notes with stale token |
| `POST` | `/api/v1/categories/{id}/archive` | archive after dependency policy |
| `POST` | `/api/v1/categories/{id}/restore` | restore archived custom category |
| `DELETE` | `/api/v1/categories/{id}` | delete eligible archived custom category |

## Directory response facts

Each item includes:

- `id`, `name`, `kind`, `isActive`, `isSystem`, `systemKey`, `notes`;
- `operationCount` — confirmed operations for user-facing usage;
- `ruleCount`, `activeRuleCount`;
- `updatedAt`;
- server capabilities `canUpdate`, `canArchive`, `canRestore`, `canDelete`;
- lifecycle/delete blocker codes and counts where relevant.

Directory capabilities include `canCreate` and stable read-only reason. Kind
options may include server-provided value/label/description so the browser does
not invent financial meaning. System facts остаются read-only.

API возвращает authoritative complete directory. При ожидаемом размере в
десятки rows search/view остаются URL-owned client projection; server counts и
capabilities не вычисляются из visible rows.

## Detail response

Query parameters:

- `date_from`, `date_to`;
- `currency` (одна доступная workspace currency);
- `type=income|expense`;
- `operations_page`, bounded `operations_page_size`.

Response includes category summary/capabilities, applied filters, available
currencies, money summary, operation page and bounded linked-rule preview.
Operation DTO содержит уже подготовленные date/type/account/description/
property/signed amount/currency facts. Browser только форматирует values.

Rules preview не копирует Rule editing policy. До Transaction Rules cutover он
ведёт в historical `/rules#rule-<id>`; после него — в canonical React route.

`return_to` — navigation-only query React route, не API parameter. Route
принимает только local `/app/reports` URL, повторяя текущую open-redirect guard.

## Mutation contracts

- create/update normalize whitespace and return exact field errors;
- name `maxLength=255`, notes `maxLength=1000` (зафиксировано в Slice 02);
- update includes `expectedUpdatedAt`;
- lifecycle/delete include `expectedStatus` and `expectedUpdatedAt`;
- all writes require API financial-write context and CSRF;
- responses return committed item/detail plus explicit impact;
- no optimistic reference/financial mutation in React.

Stable errors:

```text
category_not_found                 404
category_validation_error          422 + fieldErrors
category_update_conflict           409
category_lifecycle_conflict        409
category_archive_blocked           422 + blockers
category_delete_blocked            422 + blockers
category_system_immutable          422
```

Cross-workspace IDs use the same not-found response and never leak existence.

## State ownership

| State | Owner |
| --- | --- |
| directory `view`, `search` | URL |
| detail period/currency/type/page/return_to | URL |
| directory/detail snapshots and capabilities | loader/API server state |
| create/edit drafts, open panel, pending/retry/dialog | feature-local React |
| profit eligibility, counts, blockers, permissions, system immutability | server only |
| visual labels/formatting/focus | React/UI Foundation |

On conflict React reloads authoritative snapshot and preserves the user's draft
until explicit retry/discard. On success it replaces committed item/detail,
closes the relevant surface, moves focus predictably and shows Toast.
