# Slice 03: Document Detail And Management

Статус: planned.

## Outcome

Пользователь открывает React document detail, понимает текущий этап импорта,
видит validation/raw-row/parse history и выполняет только разрешённые reparse,
ignore или delete actions.

## API/application

Добавить:

```text
GET    /api/v1/imports/documents/{document_id}
POST   /api/v1/imports/documents/{document_id}/reparse
POST   /api/v1/imports/documents/{document_id}/ignore
DELETE /api/v1/imports/documents/{document_id}
```

Основной read response содержит:

- document/account identity и persisted status;
- workflow facts и next-step kind;
- validation/control-total summary;
- bounded raw transaction summaries;
- parse-attempt summaries;
- capabilities и stable blocking reason codes.

Не возвращать `storage_key` и filesystem path. Полный raw text/tables, если
остаётся продуктовым debug workflow, вынести в отдельный lazy,
permission-checked и size-bounded endpoint.

Mutations вызывают существующие use cases. Response reparse/ignore возвращает
новый committed document snapshot. Delete возвращает подтверждённый tombstone
result/identity. Для stale или запрещённого действия использовать `409`, а не
полагаться на скрытую кнопку.

## Frontend state/UI

- Route: `/app/imports/documents/:documentId`.
- Workflow rail и primary next step строятся из server facts.
- Raw rows и parse history имеют bounded initial rendering/disclosure.
- Destructive actions требуют явного confirmation и сохраняют focus contract.
- Reparse не optimistic: pending state показывается до authoritative response.
- После ignore/delete navigation следует server result, а не локальному
  предположению.
- Technical debug не блокирует primary workflow и загружается только по запросу.

## Tests

Backend:

- workspace isolation и not-found masking;
- viewer/manager capability matrix;
- workflow state matrix;
- validation/raw/parse attempt projection;
- reparse prohibition для confirmed rows;
- ignore/delete prohibition для linked operations;
- parse failure после reparse сохраняет attempt/document;
- delete storage/database behavior;
- stale repeated mutations.

Frontend:

- loading/error/not-found/readonly states;
- each workflow next step;
- validation и parse failure presentation;
- bounded rows/history disclosure;
- confirm/cancel/focus для ignore/delete;
- server `409/422` reconciliation;
- lazy debug не запрашивается до раскрытия;
- links в React review и mapping.

Browser:

- known parser document;
- failed parser document;
- needs-mapping document;
- reparse;
- ignore/delete allowed;
- destructive action blocked after state change;
- desktop/tablet/mobile geometry.

## Replacement/delete

После gate удалить:

- detail/reparse/ignore/delete HTML branches из `routes/documents.py`;
- `presentation/document_page/*`;
- detail-only dependencies из `presentation/documents.py`;
- `templates/imports/detail.html` и `templates/imports/detail/*`;
- detail-only shared partials, tests и CSS selectors.

Shared mapping partials/presenters остаются до Slice 04. Historical document
detail URL становится query/hash-preserving redirect.

## Exit gate

- React detail является canonical;
- management policy проверяется server-side;
- technical data exposure ограничено;
- committed action result согласован с list/review;
- old detail routes/presenter/templates удалены;
- realistic browser scenarios проходят на трёх viewport.
