# Slice 02: Statement Upload

Статус: completed.

## Outcome

Пользователь выбирает активный account, загружает PDF/XLSX, видит длительное
состояние запроса и получает ссылку на сохранённый document независимо от
успеха распознавания.

## API/application

Добавить:

```text
GET  /api/v1/imports/upload-reference
POST /api/v1/imports/documents
     Content-Type: multipart/form-data
```

Reference response содержит только активные workspace accounts, accepted file
types/size limits и `canUpload`.

Upload command переиспользует `StatementUploadUseCase`. До публикации endpoint
зафиксировать:

- idempotency/retry contract для потерянного response;
- максимальный размер файла на HTTP и storage boundary;
- stable `403`, `404`, `409`, `413`, `415`, `422` errors;
- response после parse success, needs mapping и parse failure;
- отсутствие полного exception/raw payload в error response.

Успешный HTTP response означает, что документ сохранён. Ошибка parse не должна
маскироваться как потеря upload: response возвращает document identity,
persisted status и следующий route kind.

Background queue этим slice не вводится. Синхронная обработка сохраняется, пока
реальные измерения не докажут необходимость отдельного решения.

## Frontend state/UI

- Route: `/app/imports/upload`.
- File остаётся browser-local state и не сериализуется в route/cache.
- Во время запроса повторная submit блокируется.
- UI различает upload/network failure и сохранённый document с parse failure.
- No-account state ведёт в существующий accounts workflow.
- Back/refresh не должны автоматически повторять multipart command.
- После committed response переход идёт на React/legacy detail согласно
  текущему cutover состоянию.

## Tests

Backend:

- permission и workspace-scoped account;
- unsupported type и oversized file;
- original document сохранён до parse;
- `ParseAttempt` на success/failure;
- safe parse error;
- idempotent/retry behavior;
- response next-step для known/unknown/failed statement.

Frontend:

- account/file selection;
- no-account and readonly states;
- pending/disabled submit;
- validation и server errors без потери понятного draft;
- committed parse failure ведёт в document detail;
- повторный click не создаёт второй request;
- keyboard/focus и mobile file control.

Browser:

- realistic known statement;
- realistic unknown statement;
- controlled parse failure;
- network retry/recovery в пределах принятого idempotency contract.

## Replacement/delete

После gate удалить:

- GET/POST upload branches из `routes/documents.py`;
- `UploadPagePresenter` и upload-only ViewModels;
- `templates/imports/upload.html`;
- Alpine file-name hook;
- upload-only template tests и selectors.

Historical `/imports/upload` становится query-preserving redirect на
`/app/imports/upload`.

## Exit gate

- React upload является единственным upload UI;
- документ и raw source не теряются при parse failure;
- retry policy доказана тестом;
- no-account/readonly/error states работают;
- old upload route/template/presenter удалены;
- browser upload проходит desktop/tablet/mobile.

## Completion record

Завершено 2026-07-24.

- `/app/imports/upload` стал единственным интерфейсом загрузки и использует
  typed `GET /api/v1/imports/upload-reference` и multipart
  `POST /api/v1/imports/documents`.
- Счёт выбирается явно; файл остаётся browser-local и проверяется по расширению
  и размеру до отправки. Pending блокирует повторную отправку и объясняет
  длительную синхронную обработку.
- Максимальный размер контролируется также во время streaming save. Частичный
  файл удаляется при превышении лимита.
- `Idempotency-Key` детерминированно задаёт document identity внутри workspace.
  Одинаковый account/filename/content возвращает сохранённый документ без
  повторного parse; другой payload получает `409`.
- Parse failure остаётся успешным committed upload и ведёт в React document
  detail, где виден безопасный результат обработки.
- Legacy GET стал query-preserving redirect; HTML POST, Jinja template,
  presenter, Alpine filename hook, template tests и upload-only CSS удалены.
- Canonical ссылки из списка, detail, dashboard, accounts, reports, onboarding
  и mapping ведут на React upload.
