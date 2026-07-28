# Imports Refactoring Findings

Статус: подтверждённые результаты архитектурного аудита.

## Масштаб

Исходный аудит:

- 121 Python-файл и 14 309 строк в `src/app/features/imports`;
- 269 classes/enums/dataclasses;
- 595 functions и methods;
- 201 профильный feature/API test;
- 8 190 строк в профильных test files.

Сам размер не является дефектом. Главная проблема — пересечение нескольких
причин изменения внутри одного feature и нескольких крупных файлов.

Повторный аудит после Phase 6, 2026-07-28:

- 108 Python-файлов и 14 617 строк в `imports` + `import_review`;
- 280 classes/enums/dataclasses;
- 596 functions и methods;
- внутренних import cycles нет;
- Ruff и ty проходят;
- 215 профильных feature/API tests collected;
- 199 tests вне известного sandbox-sensitive `test_imports.py` проходят.

## Приоритеты

| Priority | Finding | Последствие | Решение |
| --- | --- | --- | --- |
| Resolved | Общий reparse был реализован без текущего продуктового сценария | Race, superseded rows, лишние статусы и тесты | Удалён без изменения upload/mapping |
| Resolved | Review принадлежал `imports`, но оркестрировал ledger/rules | Циклическая feature-связанность и неясный owner транзакции | `import_review` выделен; API/chat используют общие actors |
| Resolved | Unsigned amount имел скрытый default `INCOME` | Внутренний caller мог неверно классифицировать expense | Значение обязательно; legacy template использует `REQUIRE_SIGN` |
| P1 | Duplicate evidence хранится в `normalization_error` | `MARK_UNIQUE` меняет status, но строка может оставаться заблокированной как ненормализованная | Разделить duplicate signal и normalization error в Wave C / Phase 8 |
| P2 | Review persistence остаётся в broad imports repositories | Feature extraction завершён, но read/write ownership неполон | Перенести review rows/locks/linking/queue в `ImportReviewRepository` |
| P2 | Validation reason mapping дублируется | Document Detail и Import Review могут разойтись | Один typed resolver и persisted report decoder |
| P2 | Persisted unknown-analysis JSON декодируется вручную | Много `cast`/`isinstance`, высокая стоимость изменения payload | Frozen Pydantic projection на JSON boundary |
| P2 | Parser/application импортируют enum через ORM module | Ложная зависимость на persistence | Импортировать status values из defining domain modules |
| Resolved | React compatibility routes были распределены по двум местам | Cutover сложнее проверять и завершать | Один compatibility router |
| Resolved | Unknown-statement packages были чрезмерно фрагментированы | Высокая навигационная стоимость | 22 файла сокращены до 14 без изменения алгоритмов |

P0-проблем по результатам обоих аудитов не найдено.

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

Исправлено в Phase 3.2: в domain остались fingerprint и чистая classification
policy. `RawTransactionDeduplicator`, DB lookup и mutation ORM-строк находятся в
`application/pipelines/deduplication.py`.

### `domain/validation.py`

Domain импортирует `StatementControlTotals` из parser types. Control totals —
domain value; parser должен возвращать его, а не владеть типом.

### `query_repository.py`

Persistence импортирует application filters/DTO. Repository должен возвращать
собственную typed projection, а application reader — собирать публичный
read model.

### Review ↔ ledger

Исправляется в Phase 6.6. `RawTransactionPoster` уже удалён: confirmation и
transfer orchestration принадлежат `import_review`, а `LedgerPostingService`
получает готовые финансовые facts. Imported undo также перенесён в
`import_review`; оставшаяся обратная зависимость находится в review-specific
ledger queries и raw-row helpers. Целевая схема:

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

Один внутренний snapshot сохраняется как простой компромисс для двух
read-сценариев. Он не содержит `storage_key`, SHA и raw text. `raw_tables`
остаются только потому, что нужны unknown statement mapping; публичный document
detail API их не возвращает.

### Parser strategies

Исправлено в Phase 5.1: Protocol, resolver, context и две strategy-обёртки
удалены. `StatementParseProcessor` через существующий parser registry явно
вызывает known или unknown pipeline.

### Unknown-statement analysis

Исправлено в Phase 5.2: девять analysis models собраны в
`analysis_models.py`, а локальные profiling, scoring и row-detection функции
перенесены к операциям-владельцам. Удалены compatibility-фасады и восемь лишних
границ между файлами. Пакет уменьшен с 22 до 14 Python-файлов и на 109 строк
без изменения алгоритмов.

Дополнительно исправлено в Phase 5.3: однотипная ручная сериализация вложенных
analysis models заменена на одну явную границу отчёта и `dataclasses.asdict()`.
Внутренние `column_profiles` исключены из сохраняемого JSON, а ручное
копирование continuation preview заменено на `dataclasses.replace()`. Пакет
уменьшен ещё на 81 строку без добавления новых файлов и абстракций.

Исправлено в Phase 5.4: ручной decoder `unknown_statement_hints.json` заменён на
frozen Pydantic models и `model_validate_json()`. Некорректные вложенные типы,
неизвестные поля и пустые markers больше не превращаются молча в пустые
значения. `hints.py` уменьшен на 63 строки без изменения корректной
конфигурации и алгоритмов распознавания.

Исправлено в Phase 5.5: повторяющаяся классификация mapping fields заменена
двумя локальными data tables. Confidence и reason теперь вычисляются совместно
из одного column profile; бизнес-ветвление amount против debit/credit оставлено
явным. Пакет уменьшен ещё на 38 строк без новых файлов или классов.

Пересмотрено в Phase 5.6: numeric confidence не участвовал в выборе suggestion,
порогах, auto-apply или финансовых решениях и показывался только как
некалиброванный процент. Он удалён из unknown mapping по всей цепочке. Конкретные
evidence/reasons сохранены; остальные confidence-механизмы imports не
затрагивались.

Исправлено в Phase 5.7: unknown control totals сохраняют найденные нули, не
угадывают RUB при отсутствии валюты и не используют labels чужих банков.
Неизвестная валюта разрешается через выбранный mapping/account только на
границе импорта. Четыре риска закреплены characterization tests.

Исправлено в Phase 5.8: shared header and text-fragment primitives перемещены в
`parsing/support`. Known Alfa/T-Bank parsers больше не зависят от
`application/unknown_statements`; алгоритмы не дублировались и не менялись.

Исправлено в Phase 5.9: text fallback строит полные candidate tables один раз и
использует тот же artifact для preview и `raw_tables_json`. Повторный проход по
PDF text удалён без потери строк и без расширения публичного report.

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

Mapping column/amount/control-total validation исправлена в Phase 3.4: preview
и import используют один `StatementMappingValidator`.

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
