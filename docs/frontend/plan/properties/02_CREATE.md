# Slice 02 — Create Property

Статус: completed 2026-08-01.

## User outcome

Writer создаёт Property в правом `WorkbenchPanel`, сохраняет draft при
validation/network error и после success видит committed row, Toast и
восстановленный focus. Viewer не получает mutation control.

## Application/API

```text
POST /api/v1/properties -> 201 PropertySummary response
```

Request: `name`, `shortName`, `address`. Pydantic/API validation выражает
реальные database bounds (255/64), whitespace normalization и field errors.
Empty optional strings становятся `null`; name обязателен. Duplicate names
разрешены, поскольку текущая domain model идентифицирует Property по UUID.

Endpoint использует financial-write context и header CSRF. Transaction
boundary остаётся server-owned; response — smallest truthful committed row с
capabilities и timestamps.

## React interaction

- «Новый объект» — единственная primary CTA directory;
- `WorkbenchPanel`, `Field`, `FormGrid`, `FormActions`, `FormErrorSummary`;
- dirty close вызывает shared confirmation;
- client validation улучшает feedback, но server остаётся authority;
- pending отключает повторный submit;
- 401 ведёт на login с `/app/properties` next;
- 403/422/network errors сохраняют draft; first invalid field получает focus;
- success вставляет/заменяет committed entity согласно текущему view/search,
  закрывает panel и сообщает Toast без recent query/banner.

## Tests

- service/application normalization, null optionals, max lengths, duplicate
  names и workspace ownership;
- API 201/401/403/CSRF/422 and response snapshot;
- React required/max errors, server field mapping, draft preservation,
  double-submit prevention, dirty close, focus return, authoritative insert;
- no create button/read-only explanation for viewer.

## Exit gate

- create работает end-to-end на `/app/properties`;
- SSR create остаётся доступен до cutover;
- никакой browser code не создаёт status или capability самостоятельно.

## Completion record

Implemented:

- `POST /api/v1/properties` с financial-write/CSRF boundary, нормализацией,
  database bounds и stable validation field errors;
- application create command через workspace-scoped mutation Protocol и
  server-owned committed summary/capabilities;
- React `WorkbenchPanel` с accessible fields, client/server validation,
  pending guard, dirty-close confirmation, draft preservation, Toast и focus
  restoration;
- authoritative committed row вставляется по UUID, status/capabilities не
  создаются в browser;
- realistic browser fixture создаёт Property через React API вместо SSR form.

Checks:

- backend application/API/OpenAPI tests;
- Properties API/form/page tests, включая server errors, dirty draft,
  double-submit и committed insert;
- Ruff, ty, frontend format/lint/styles/API/type/build;
- end-to-end browser audit Mocha и Latte на 1440/920/390.

Known follow-up: редактирование, optimistic concurrency и lifecycle остаются в
Slices 03–04; SSR create сохраняется до Slice 05.
