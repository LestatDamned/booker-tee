# Slice 04: Imported Operation Correction

Статус: planned.

## Outcome

Пользователь исправляет description, category и property подтвержденной
импортированной операции прямо в React account ledger, не меняя posting facts.

## API/application

Добавить:

```text
PUT /api/v1/accounts/{account_id}/operations/{operation_id}/review-fields
```

Request:

```text
expectedVersion
description
categoryId
propertyId
```

Route сначала доказывает, что operation workspace-scoped и связана MoneyEntry с
route account, затем вызывает существующий `ImportedOperationReviewUseCase`.
Application повторно проверяет:

- source `BANK_PDF`;
- status `confirmed`;
- expected operation version;
- workspace ownership category/property;
- mutation permission.

Success возвращает committed movement snapshot/capabilities. Amount, date, type,
status, source и MoneyEntry не входят в command. API не возвращает HTML partial.

Reference options загружаются side-effect-free. Persisted inactive reference
остается видимой, но новый выбор следует текущей server policy.

## Frontend state/UI

- Edit panel раскрывается локально без HTMX.
- Draft initialized from current committed movement.
- Manual operation сохраняет link в React Manual Ledger и не получает вторую
  edit form.
- System/unsupported/imported non-confirmed operation readonly по server
  capability/reason.
- `422`, `409` и network error сохраняют draft.
- Pending блокирует repeated submit.
- Success reconciles committed movement, version и capabilities.
- Source row/document link остается доступен рядом с correction.

## Tests

Backend:

- account/workspace/operation association;
- viewer/editor permission;
- source/status capability matrix;
- optimistic version conflict;
- category/property workspace isolation;
- изменяются только разрешенные fields;
- transaction rollback;
- response отражает новую committed version.

Frontend:

- capability-aware edit/readonly states;
- accessible panel, labels, error summary и focus;
- draft survives errors;
- stale conflict/reload flow;
- manual/import/system action distinction;
- committed row reconciliation без optimistic money changes.

## Replacement/delete

После gate удалить historical HTMX:

```text
GET  /accounts/{account_id}/operations/{operation_id}/review-fields/edit
POST /accounts/{account_id}/operations/{operation_id}/review-fields
```

Удалить edit-panel partial, row replacement response, HTMX attributes,
presenter drawer ViewModels и replacement-only tests.

## Exit gate

- correction имеет одну JSON mutation surface;
- operation/account/workspace association доказана server tests;
- optimistic conflict не теряет draft;
- manual operation продолжает редактироваться только в Manual Ledger;
- HTML fragments/HTMX account correction отсутствуют.
