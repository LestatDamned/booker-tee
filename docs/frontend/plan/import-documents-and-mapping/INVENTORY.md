# Inventory: Import Documents And Mapping

Статус: baseline перед Stage 07 implementation.

Проверено: 2026-07-23.

## Scope

В scope входят оставшиеся authenticated Imports pages:

```text
GET/POST /imports
GET/POST /imports/upload
GET      /imports/documents/{document_id}
POST     /imports/documents/{document_id}/reparse
POST     /imports/documents/{document_id}/ignore
POST     /imports/documents/{document_id}/delete
GET/POST /imports/documents/{document_id}/mapping
POST     /imports/documents/{document_id}/mapping/import
```

Не входит уже мигрированный:

```text
/app/imports/documents/{document_id}/review
/api/v1/imports/documents/{document_id}/review/*
```

Также не входят широкие изменения parsers, ledger, accounts, chat transport,
storage backend или background processing infrastructure.

## Наблюдаемый flow

### Список

- Показывает filename, account, upload time и document status.
- Primary action зависит от state: document detail, mapping или React review.
- Есть warning/complete/ignored визуальные состояния и empty state.
- Возможность upload зависит от import-management permission.

### Upload

- Загружает PDF/XLSX через multipart form.
- Требует существующий активный account текущего workspace.
- Сохраняет файл и `UploadedDocument` до parse.
- Создаёт отдельный `ParseAttempt`.
- Сохраняет документ и безопасную ошибку при parse failure.
- После завершения ведёт на document detail.

Текущая обработка выполняется синхронно в request. SHA-256 хранится и
индексируется, но upload command не имеет строгого idempotency contract.

### Document detail

- Показывает workflow: extraction, mapping, review, completion.
- Показывает document/account summary и validation/control totals.
- Для unknown statement показывает найденные таблицы и mapping suggestions.
- Показывает raw transactions и parse-attempt history.
- Имеет reparse, ignore и delete actions.
- Показывает technical debug: SHA-256, storage key, raw tables и raw text.

Reparse запрещён при confirmed rows. Ignore и delete запрещены, если raw rows
имеют linked operations.

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
- `StatementReparseUseCase`;
- `ImportDocumentManagementUseCase`;
- `ImportService` и document detail/read queries после выделения typed
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

## Legacy implementation/delete manifest

### Routes

- `src/app/features/imports/routes/documents.py`;
- `src/app/features/imports/routes/mapping.py`;
- HTML router includes в `src/app/features/imports/router.py`.

После cutover файлы заменяются минимальными compatibility redirects либо
удаляются, если redirects принадлежат общему React adapter.

### Presenters

- `src/app/features/imports/presentation/documents.py`;
- `src/app/features/imports/presentation/document_page/*`;
- `src/app/features/imports/presentation/mapping/*`;
- `src/app/features/imports/presentation/field_labels.py`;
- `src/app/features/imports/presentation/mapping_suggestions.py`.

Последние два файла удаляются только после detail и mapping consumer search.

### Templates

- `src/app/templates/imports/index.html`;
- `src/app/templates/imports/upload.html`;
- `src/app/templates/imports/detail.html`;
- `src/app/templates/imports/detail/*`;
- `src/app/templates/imports/mapping.html`;
- `src/app/templates/imports/mapping/*`;
- shared imports partials `_action_details.html`, `_document_summary.html`,
  `_mapping_candidates.html`, `_mapping_suggestion.html`, `_page_hero.html`,
  `_raw_transaction_row.html`, `_workflow_steps.html`.

### Tests to replace, not blindly port

- `tests/features/imports/test_import_detail_template.py`;
- `tests/features/imports/test_import_document_detail_presentation.py`;
- Imports portions of `test_user_guide_templates.py`;
- route/template assertions in reports, accounts, workspaces and shell tests.

Domain/application/parser/deduplication/storage tests remain. Assertions that
encode product behavior move to API/application or React tests; assertions only
about deleted Jinja markup are removed.

### Assets and tooling

- Imports-specific blocks in `src/app/static/css/app.css`;
- Alpine file-name behavior on upload;
- legacy page definitions and selectors in `scripts/ui_audit.py`;
- generated OpenAPI entries for deleted HTML routes.

Global legacy CSS удаляется только после последнего authenticated/public
consumer; Imports-specific selectors удаляются вместе с последним Imports
template consumer.

## Known risks to resolve in implementation

1. Upload retry может создать второй document после потерянного response.
2. Parse/reparse — длительные синхронные операции без background queue.
3. Raw tables/text могут сделать JSON слишком большим и раскрыть лишние данные.
4. Mapping preview может потерять draft при `422`, network error или Back.
5. Stale UI может повторить reparse/ignore/delete после изменения lifecycle.
6. Mapping import retry может повторно создать raw rows.
7. Viewer и manager должны видеть разные capabilities, но один status truth.
8. Ссылки из dashboard/chat/accounts могут оставить пользователя в legacy UI.
