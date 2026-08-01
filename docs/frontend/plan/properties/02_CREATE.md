# Slice 02 — Create Property

Статус: planned.

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

