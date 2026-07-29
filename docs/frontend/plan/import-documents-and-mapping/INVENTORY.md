# Inventory: Import Documents And Mapping

Статус: active inventory; Slices 01–04 cutover завершены.

Проверено: 2026-07-24.

## Scope

В scope общего cutover остаются authenticated Imports entry points:

```text
GET /imports
```

Уже мигрированы:

```text
/app/imports
/app/imports/upload
/app/imports/documents/{document_id}
/app/imports/documents/{document_id}/mapping
/app/imports/documents/{document_id}/review
/api/v1/imports/*
```

Также не входят широкие изменения parsers, ledger, accounts, chat transport,
storage backend или background processing infrastructure.

## Наблюдаемый flow

### Список

- Показывает filename, account, upload time и document status.
- Primary action зависит от state: document detail, mapping или React review.
- Есть warning/complete/ignored визуальные состояния и empty state.
- Возможность upload зависит от import-management permission.

### Upload — React

- Загружает PDF/XLSX через multipart form.
- Требует существующий активный account текущего workspace.
- Сохраняет файл и `UploadedDocument` до parse.
- Создаёт отдельный `ParseAttempt`.
- Сохраняет документ и безопасную ошибку при parse failure.
- После завершения ведёт на document detail.
- Ограничивает streaming upload 20 МБ по умолчанию.
- Повторяет потерянный response по `Idempotency-Key` без второго документа и
  повторного parse.

Текущая обработка выполняется синхронно в request. SHA-256 хранится и
индексируется; command idempotency отделена от дедупликации банковских строк.

### Document detail — React

- Показывает workflow: extraction, mapping, review, completion.
- Показывает document/account summary и validation/control totals.
- Показывает bounded raw transaction summaries и parse-attempt history.
- Имеет permission- и capability-aware ignore и delete actions через
  JSON API с expected-status guard.
- Не публикует SHA-256, storage key, raw tables или raw text.

Ignore и delete запрещены, если raw rows имеют linked operations.

### Mapping

- Выбирает table по page/table identity.
- Поддерживает поля `operation_date`, `posting_date`, `description`, `amount`,
  `debit`, `credit`, `balance`, `currency`.
- Поддерживает first data row и default currency.
- Показывает analyzer suggestions, column candidates и warnings.
- Выполняет server-side preview и показывает row-level errors.
- Может сохранить mapping template.
- Import создаёт reviewable raw rows и ведёт в React Import Review.

## Existing application boundary

Сохраняются и переиспользуются:

- `StatementUploadUseCase`;
- `ImportDocumentManagementUseCase`;
- `DocumentRepository.get_document_snapshot(...)` и document detail/read
  projections;
- `UnknownStatementMappingImportUseCase`;
- mapping preview/default/analyzer code;
- extraction resolver и upload storage;
- parse processor, known parsers и unknown fallback;
- deduplication, repositories и persistence models.

JSON routes не вызывают legacy HTML routes и не используют Jinja presenters как
свой контракт.

## Data exposure decisions

Основной document DTO может содержать:

- document identity, filename, type, persisted status;
- account reference;
- uploaded/updated timestamps и file size;
- validation/control-total summary;
- bounded raw-row summary;
- parse-attempt summary;
- server capabilities и stable blocking reason codes.

Основной DTO не содержит:

- `storage_key`;
- filesystem path;
- полный raw text;
- полный набор извлечённых таблиц;
- произвольные internal exception payloads.

Если technical debug сохраняется как пользовательская возможность, он
загружается отдельным permission-checked endpoint только после явного
раскрытия. Response ограничивает размер и маскирует чувствительные значения.

## Geometry baseline

Realistic UI audit выполнен для:

- `/imports`;
- `/imports/upload`;
- document detail;
- document mapping.

Проверены `1440×1000`, `920×900` и `390×844`: всего 12 страниц, baseline прошёл.

Replacement должен сохранить:

- отсутствие horizontal page overflow;
- читаемый status/action hierarchy;
- одну основную задачу на страницу;
- card/table dual representation для широких tabular данных;
- доступность primary action без поиска в длинном debug content;
- работоспособный mapping form на mobile без горизонтальной формы.

Mapping — критическая geometry page: picker, 8 column mappings, preview,
suggestions и source table должны оставаться различимыми, но не обязаны
одновременно находиться в viewport.

## Cross-feature consumers

Ссылки на Imports найдены в:

- `frontend/app/shell/app-shell.tsx`;
- existing Import Review back/document links;
- legacy `base.html`;
- dashboard summary;
- reports;
- accounts list/detail;
- onboarding checklist;
- authenticated home quick actions;
- chat integration menu/url builder;
- `scripts/ui_audit.py`;
- workspace return-path tests.

Cutover обязан обновить каждый runtime consumer или сознательно оставить
historical redirect. Нельзя считать миграцию завершённой только по смене
Imports navbar link.

## Legacy implementation/delete manifest — completed

- `src/app/features/imports/router.py`, `routes/` и `presentation/` удалены;
- imports Jinja templates и HTML mutation routes отсутствуют;
- historical GET compatibility принадлежит
  `src/app/legacy_frontend_redirects.py`;
- React/API tests заменили удалённые presenter/template contracts;
- domain/application/parser/deduplication/storage tests сохранены;
- Imports-specific `.workflow-step*` удалены после runtime и dynamic-class
  consumer search;
- historical HTML route удалён из generated OpenAPI.

Global legacy CSS остаётся только для реально существующих SSR consumers других
features и удаляется вместе с их отдельными React cutover.

## Known risks to resolve in implementation

1. Upload retry может создать второй document после потерянного response.
2. Parse при upload — длительная синхронная операция без background queue.
3. Raw tables/text исключены из основного detail DTO; отдельный debug endpoint
   не добавлен, пока не доказана продуктовая потребность.
4. Mapping preview может потерять draft при `422`, network error или Back.
5. Ignore/delete используют expected status и повторную server policy check;
   дальнейшая версия документа понадобится только при более тонких same-status
   гонках.
6. Mapping import retry может повторно создать raw rows.
7. Viewer и manager должны видеть разные capabilities, но один status truth.
8. Ссылки из dashboard/chat/accounts могут оставить пользователя в legacy UI.
