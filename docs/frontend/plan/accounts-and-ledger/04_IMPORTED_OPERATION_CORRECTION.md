# Slice 04: Imported Operation Correction

Статус: completed.

Completed: 2026-07-30.

Implemented:

- workspace/account-scoped JSON mutation над существующим
  `ImportedOperationReviewUseCase`;
- server capabilities для каждой account movement;
- React inline row expansion для description/category/property с committed
  reconciliation, совпадающий с паттерном Manual Ledger;
- общий с Import Review searchable category selector и split actions;
- optimistic version conflict, field errors, focus и сохранение draft;
- исходная строка остаётся отдельным действием самой movement row, без
  дублирования нефункционального контента внутри формы.

Checks run:

- backend Ruff, ty и focused pytest;
- frontend Prettier, ESLint, Stylelint, generated API check, TypeScript и Vitest;
- production build и realistic Playwright audit на `1440`, `920` и `390`.

Intentional deviations:

- realistic browser fixture превращает существующую проводку в editable imported
  movement на уровне перехваченного read response; настоящий API mutation и
  association отдельно проверены server и React interaction tests.

Cleanup performed:

- удалены historical HTMX correction GET/POST;
- удалены correction drawer/edit partials, presenter ViewModels, HTMX row
  replacement attributes и replacement-only tests/CSS.

Measurements/risks:

- amount, date, type, source, status и MoneyEntry не входят в correction command;
- committed row заменяется только ответом сервера, browser не пересчитывает
  денежные значения.

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

- Edit panel раскрывается локально под выбранной строкой через общий
  `ExpansionPanel`, без HTMX и бокового drawer.
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
