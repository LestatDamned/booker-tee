# Slice 04: Unknown Statement Mapping

Статус: planned.

## Outcome

Пользователь выбирает исходную таблицу, настраивает колонки, получает
authoritative server preview, исправляет warnings/errors, при необходимости
сохраняет template и создаёт reviewable raw rows ровно один раз.

## API/application

Добавить:

```text
GET  /api/v1/imports/documents/{document_id}/mapping
POST /api/v1/imports/documents/{document_id}/mapping/preview
POST /api/v1/imports/documents/{document_id}/mapping/import
```

Mapping read содержит:

- document identity/status/account/currency;
- capability и blocking reason;
- saved template/default mapping facts;
- bounded table summaries, column candidates и suggestions;
- stable field/warning/error codes.

`table_ref` становится typed identity:

```json
{
  "pageNumber": 1,
  "tableIndex": 0
}
```

Preview request содержит явный mapping command. Preview остаётся server-side и
не создаёт raw rows. Response ограничивает количество preview rows и отдельно
возвращает total/invalid counts.

Import request использует тот же typed command, optional template name и
idempotency key. Он вызывает существующий mapping import use case,
deduplication и document lifecycle. Успех возвращает committed document/review
summary и canonical review target kind.

## Frontend state/UI

- Route: `/app/imports/documents/:documentId/mapping`.
- Mapping draft feature-local; server document/table data не копируются в draft.
- Выбор table может отражаться в query parameter для Back/Forward, если это
  доказано interaction test; все восемь mapping fields в URL не помещаются.
- Preview не очищает draft при `422`, `409` или network error.
- Import не optimistic и блокирует повторную submit.
- Source table, mapping form и preview имеют раздельную visual hierarchy.
- Desktop использует доступную ширину таблиц; mobile использует card/stack
  representation без horizontal page overflow.
- Labels/tones/copy принадлежат frontend, warning semantics — server.

## Tests

Backend:

- workspace isolation и management permission;
- document lifecycle/capability;
- typed table identity;
- saved-template ownership;
- all supported column roles;
- duplicate role, missing required role и invalid row errors;
- bounded preview и deterministic row ordering;
- preview не мутирует persistence;
- import создаёт только reviewable raw rows;
- deduplication и idempotent replay;
- template save и conflicting idempotency payload;
- successful transition в existing React review.

Frontend:

- defaults и saved template;
- switching tables;
- all mapping controls and accessible labels;
- draft survives preview/error;
- warnings, candidates и row errors;
- no-table/readonly/stale states;
- pending/repeated import;
- keyboard order, focus и responsive table/card views.

Browser:

- single-table suggested mapping;
- multiple-table selection;
- debit/credit mapping;
- amount mapping;
- invalid preview followed by correction;
- optional template save;
- import followed by canonical React review;
- desktop/tablet/mobile without overflow or console/request errors.

## Replacement/delete

После gate удалить:

- `routes/mapping.py`;
- `presentation/mapping/*`;
- `templates/imports/mapping.html` и `templates/imports/mapping/*`;
- оставшиеся mapping-only shared imports partials;
- `presentation/field_labels.py` и `mapping_suggestions.py` после consumer search;
- mapping template/presentation tests и selectors.

Historical mapping GET становится query-preserving redirect. Historical preview
и import form POST endpoints удаляются, а не превращаются в постоянную вторую
mutation surface.

## Exit gate

- full unknown-statement mapping работает только в React/API;
- preview и import остаются server-authoritative;
- retry не создаёт raw rows повторно;
- draft/error/back behavior доказаны interaction tests;
- mapping ведёт в существующий canonical React review;
- legacy mapping routes/presentation/templates удалены;
- realistic browser mapping проходит на трёх viewport.
