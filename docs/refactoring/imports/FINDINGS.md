# Imports Refactoring Findings

Статус: подтверждённые результаты архитектурного аудита.

## Масштаб

На момент аудита:

- 121 Python-файл и 14 309 строк в `src/app/features/imports`;
- 269 classes/enums/dataclasses;
- 595 functions и methods;
- 201 профильный feature/API test;
- 8 190 строк в профильных test files.

Сам размер не является дефектом. Главная проблема — пересечение нескольких
причин изменения внутри одного feature и нескольких крупных файлов.

## Приоритеты

| Priority | Finding | Последствие | Решение |
| --- | --- | --- | --- |
| Resolved | Общий reparse был реализован без текущего продуктового сценария | Race, superseded rows, лишние статусы и тесты | Удалён без изменения upload/mapping |
| P1 | Review принадлежит `imports`, но оркестрирует ledger/rules | Циклическая feature-связанность и неясный owner транзакции | Выделить `import_review` |
| Resolved | Unsigned amount имел скрытый default `INCOME` | Внутренний caller мог неверно классифицировать expense | Значение обязательно; legacy template использует `REQUIRE_SIGN` |
| P2 | Два broad repositories | Persistence меняется по несвязанным причинам | Split document/mapping/review repositories |
| P2 | Domain импортирует ORM/repository/parser types | Направление зависимостей нарушено | Оставить в domain только policies и values |
| P2 | React compatibility routes распределены по двум местам | Cutover сложнее проверять и завершать | Один compatibility router |
| P2 | Исторические `/imports/...` ещё используются | Лишние redirect hops, delete gate не пройден | Перевести consumers на `/app/imports/...` |
| P3 | Unknown-statement packages чрезмерно фрагментированы | Высокая навигационная стоимость | Консолидация по устойчивым обязанностям |

P0-проблем по результатам аудита не найдено.

## Resolved scope decision: общий reparse удалён

Удалённый `StatementReparseUseCase`:

1. блокирует document;
2. создаёт `ParseAttempt(status=running)`;
3. делает commit и освобождает document lock;
4. выполняет extraction;
5. supersede-ит старые rows и создаёт новые.

Это создаёт race и сложную замену существующих rows. При этом сейчас существует
только одна версия parser для каждого банка, нет массового reprocessing и нет
выбора между результатами разных версий.

Выполнено:

- удалить пользовательскую кнопку и API endpoint;
- удалить `StatementReparseUseCase`;
- удалить reparse-specific supersede flow, если у него нет других consumers;
- сохранить `ParseAttempt` как историю единственной обработки при upload;
- versioning, retry, stale-attempt recovery и административный reprocess не
  добавлялись.

Повторная обработка возвращается только после появления подтверждённого
сценария и проектируется заново по его требованиям.

## Deferred: overlapping-statement deduplication

Междокументная deduplication остаётся действующим контрактом и не связана с
reparse. Во время структурного рефакторинга её поведение сохраняется без
расширения.

Отдельная последняя фаза проверит сценарий выписок с пересекающимися периодами,
модель exact/possible duplicate, `MARK_UNIQUE` и конкурентное подтверждение.

## Реальная feature-граница

Оставить в `imports`:

- `UploadedDocument`, `ParseAttempt`, `RawTransaction`;
- storage и extraction;
- parser registry и bank parsers;
- known/unknown statement processing;
- mapping templates/executions;
- statement validation и import deduplication.

Перенести в `import_review`:

- queue/read model;
- classification и confirmability;
- lifecycle actions;
- duplicate evidence;
- confirmation;
- transfers;
- user-triggered rule application;
- undo posting.

Persistence-модели остаются в `imports`, чтобы не создавать искусственную
миграцию одного import-source aggregate.

## Нарушения слоёв

### `domain/deduplication.py`

`RawTransactionDeduplicator` зависит от ORM `RawTransaction` и concrete
`ImportRepository`. Это application orchestration. В domain должны остаться
fingerprint и mutation policy над facts/protocol.

### `domain/validation.py`

Domain импортирует `StatementControlTotals` из parser types. Control totals —
domain value; parser должен возвращать его, а не владеть типом.

### `query_repository.py`

Persistence импортирует application filters/DTO. Repository должен возвращать
собственную typed projection, а application reader — собирать публичный
read model.

### Review ↔ ledger

Import review напрямую создаёт `RawTransactionPoster`, ledger repository и
transaction-rule use cases. Ledger в ответ знает об imports models/status
refresh. Целевая схема:

```text
ImportReview application owns transaction
  -> LedgerPostingService posts money facts
  -> ImportReviewRepository links row and refreshes review/document
```

Event bus для этого не требуется.

## Избыточные слои

### Document detail — исправлено в Commit 2.3

Удалена цепочка:

```text
reader
  -> ImportService
  -> ImportQueryRepository
  -> ORM
  -> ImportDocumentDetailViewMapper
  -> ImportDocumentDetailView
  -> public read model
  -> API mapper
```

Текущая цепочка:

```text
reader
  -> ImportQueryRepository.get_document_snapshot()
  -> ImportDocumentSnapshot
  -> public read model
  -> API schema
```

Внутренний snapshot сохраняется: он ограничивает выход `storage_key`, SHA,
raw text и tables в публичный API.

### Parser strategies

Для двух статических ветвей существует Protocol, resolver, context и две
strategy-обёртки поверх known/unknown pipelines. Достаточно одного
`StatementProcessor`, выбирающего `KnownStatementProcessor` или
`UnknownStatementProcessor` через существующий parser registry.

## Cleanup-кандидаты

В Commit 2.1 удалены:

- `RawTransactionReviewUseCase`;
- `raw_transaction_status_for_review_action`;
- `mapped_rows_to_drafts`;
- `mapped_row_to_draft`;
- `raw_transaction_status_for_mapped_row`;
- `mapped_row_source_id`;
- test-only `preview_unknown_statement_mapping`;
- `compatible_mapping_table_count`;

Ранее, в Phase 1, удалены `validate_pdf_upload` и пустой `presentation`
package.

В Commit 2.2 устранены:

- `append_review_message`;
- integer JSON conversion;
- latest parse-attempt selection;
- control-total JSON decoding;

Следующие более крупные дубли остаются для поздних этапов:

- validation reason mapping;
- mapping column/amount validation.

## React cutover

Imports-specific Jinja/HTMX/Alpine runtime уже отсутствует. Остались GET
compatibility redirects и historical URL consumers.

Безопасный порядок:

1. перевести React, templates и UI audit на `/app/imports/...`;
2. собрать GET redirects в React compatibility router;
3. удалить imports `router.py`, `routes/` и пустой `presentation/`;
4. сохранять redirects до отдельного compatibility decision.

Legacy CSS `.workflow-step*` удалён после consumer search: runtime и
динамические class consumers не найдены.
