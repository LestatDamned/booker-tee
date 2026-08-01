# Slice 03 — Edit Property

Статус: completed 2026-08-01; использует README decision D3.

## User outcome

Writer раскрывает editor под конкретной row, меняет name/short name/address и
получает committed snapshot. Одновременно открыт максимум один editor; close и
validation сохраняют предсказуемый focus/draft contract.

## Application/API

```text
PUT /api/v1/properties/{property_id}
```

Request повторяет editable fields и содержит `expectedUpdatedAt`. Endpoint:

- разрешает только financial writer;
- ищет Property по `(workspace_id, property_id)`;
- возвращает 404 без раскрытия foreign entity;
- валидирует bounds/normalization как create;
- возвращает `409 property_update_conflict` при stale token;
- commit-ит и возвращает полный summary/capabilities snapshot.

Нужен named command/use case либо сфокусированное расширение текущего service;
Jinja presenter и React draft не участвуют в domain workflow.

## React interaction

- action использует `aria-controls`/`aria-expanded` и shared `ExpansionPanel`;
- open переводит focus в первое поле; close возвращает trigger;
- switching row с dirty draft требует confirmation;
- server field errors остаются рядом с controls, conflict предлагает
  «Обновить данные» и не затирает draft без выбора пользователя;
- success заменяет только row authoritative response и сообщает Toast;
- archive status сам по себе не запрещает metadata edit, если server capability
  это разрешает.

## Tests

- application/API workspace isolation, 404, validation, committed timestamps,
  stale 409;
- React open/close/switch, dirty confirmation, field focus, draft preservation,
  conflict recovery и row replacement;
- keyboard order и mobile expansion layout.

## Exit gate

- edit parity с SSR достигнут без last-write-wins;
- no feature CSS imports из Accounts/Manual Ledger;
- SSR edit остаётся до Slice 05.

## Completion record

Implemented:

- workspace-scoped `PUT /api/v1/properties/{property_id}` с financial-write и
  CSRF boundary, общей create/edit normalization и committed summary response;
- optimistic concurrency через обязательный `expectedUpdatedAt`, stable
  `404 property_not_found` и `409 property_update_conflict` без раскрытия
  foreign workspace entity;
- application mutation Protocol и service workflow, который проверяет stale
  snapshot до mutation, commit-ит и refresh-ит authoritative timestamp;
- inline editor для desktop table и mobile records на shared
  `ExpansionPanel`, с одним logical open editor, `aria-controls`, focus return,
  dirty switch/close confirmation и редактированием archived metadata;
- client/server validation, draft preservation, explicit conflict reload,
  authoritative row replacement и Toast;
- realistic browser fixture теперь проходит create и edit через React API.

Checks:

- backend Properties application/service/API/OpenAPI tests;
- Properties API/page tests для write permission, workspace identity, stale
  conflict, focus, dirty switch, conflict recovery и committed token;
- Ruff, ty, frontend format/lint/styles/API/type/build;
- end-to-end browser audit Mocha и Latte на 1440/920/390.

Known follow-up: archive/restore и row action competition остаются в Slice 04;
SSR edit сохраняется до replacement gate Slice 05.
