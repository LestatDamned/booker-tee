# Imports Refactoring Roadmap

Статус: рекомендуемая последовательность реализации.

Каждая фаза сохраняет рабочий продукт. Не объединять behavioral fix,
перемещение feature и массовое переименование в один commit.

## Целевая структура

```text
src/app/features/
  imports/
    models.py
    errors.py
    document_repository.py
    mapping_repository.py

    application/
      documents/
        upload.py
        management.py
        listing.py
        detail_reading.py
      statement_processing/
        processor.py
        known_statement.py
        unknown_statement.py
      mapping/
        reader.py
        engine.py
        validation.py
        importing.py
        templates.py
        contracts.py
        analysis.py

    domain/
      document_lifecycle.py
      statement_validation.py
      deduplication.py
      types.py

    infrastructure/
      storage.py
      extraction/
      parsers/

  import_review/
    errors.py
    repository.py

    application/
      reading.py
      classification.py
      lifecycle.py
      confirmation.py
      transfers.py
      rules.py
      undo.py

    domain/
      classification.py
      confirmability.py
      lifecycle.py
      queue.py
      types.py
```

## Phase 0 — Remove speculative reparse

### Commit 0.1: characterize current upload outcome

Статус: completed 2026-07-27.

- сохранить tests успешного upload, parse failure и raw-source preservation;
- зафиксировать delete restrictions для linked/confirmed данных;
- подтвердить, что mapping и обычный upload не зависят от reparse.

Exit: удаление reparse не меняет upload, mapping и import review.

### Commit 0.2: remove public reparse

Статус: completed 2026-07-27.

- удалить React action/capability;
- удалить API endpoint и reparse-specific schemas;
- удалить `StatementReparseUseCase`;
- удалить reparse-specific tests;
- удалить `supersede_existing_rows`, если после проверки consumers он больше
  не нужен.

Не добавлять parser versioning, retry endpoint, stale-attempt recovery или
административный reprocess как задел.

### Commit 0.3: safe unsigned amounts

Статус: completed.

- у `StatementMappingSpec` убран default `INCOME`;
- API требует explicit direction;
- новый UI начинает с `REQUIRE_SIGN`;
- legacy mapping template без сохранённого направления восстанавливается как
  `REQUIRE_SIGN` и не превращает сумму в доход молча.

Exit: unsigned amount никогда молча не становится income.

Phase exit: продукт поддерживает одну обработку документа при upload, а
`ParseAttempt` сохраняет её результат и диагностические данные.

## Phase 1 — Finish React cutover

### Commit 1.1: canonical links

Статус: completed.

- обычные React links → `/app/imports/...`;
- router-internal `to`/`navigate` остаются basename-relative `/imports/...`,
  что в браузере даёт `/app/imports/...`;
- legacy templates → `/app/imports/...`;
- `scripts/ui_audit.py` использует canonical URLs, кроме отдельной проверки
  historical redirect.

### Commit 1.2: consolidate redirects

Статус: completed.

- один compatibility router;
- сохранить query string и 307 behavior;
- удалить imports-specific router registration.

### Commit 1.3: remove empty legacy shell

Статус: completed.

- удалены `router.py`, `routes/` и пустой `presentation/`;
- удалены legacy CSS selectors `.workflow-step*` без runtime consumers;
- redirect tests принадлежат общему frontend compatibility router.

Exit: внутри imports нет SSR runtime/presentation.

## Phase 2 — Cheap cleanup before moves

### Commit 2.1: remove dead adapters

Статус: completed.

- удалены восемь подтверждённых production-unused forwarding/test-only
  adapters из review и unknown statement mapping;
- полезные mapping assertions переведены на production actors
  `UnknownStatementDraftMapper`, `StatementMappingEngine.apply`
  и `compatible_mapping_tables`;
- удалены три теста, проверявшие только отсутствующий production workflow или
  однострочный forwarding adapter.

Public API и пользовательское поведение не изменены.

### Commit 2.2: deduplicate pure helpers

Статус: completed.

- `append_review_message` перенесён к domain review messages и используется
  deduplication policy и repository;
- raw table decoding использует общий mapping `int_value`;
- выбор последней попытки и decoding сохранённых control totals собраны рядом с
  lifecycle `ParseAttempt`;
- добавлен workflow test, который закрепляет выбор попытки по максимальному
  `started_at`, независимо от порядка загруженного списка.

Строгий integer decoder document DTO оставлен локальным: в отличие от mapping
JSON он намеренно не преобразует строки в числа.

### Commit 2.3: document snapshot

Статус: completed.

- `ImportDocumentDetailView` переименован в `ImportDocumentSnapshot`, а
  `ImportParseAttemptView` — в `ImportParseAttemptSnapshot`;
- `ImportQueryRepository.get_document_snapshot(...)` возвращает внутренний
  read snapshot с обязательным workspace filter;
- snapshot не содержит storage key, SHA, raw text и другие поля без active
  consumers; `raw_tables` остаются для unknown statement mapping;
- document detail и unknown mapping readers зависят от узких snapshot reader
  Protocols;
- forwarding facade `ImportService` и его неиспользуемый `get_document`
  удалены;
- API composition roots передают readers непосредственно
  `ImportQueryRepository`.

Exit: меньше слоёв без изменения API.

### Commit 2.4: statement mapping engine

Статус: completed 2026-07-28.

- переиспользуемая настройка колонок названа `StatementMappingSpec`, а не
  одноразовой command;
- чистое преобразование таблиц принадлежит
  `StatementMappingEngine.apply(...)`;
- preview и import используют общий `StatementMappingResult`;
- временная нормализованная строка названа `MappedStatementRow`;
- `mapping_defaults.py` атомарно выбирает default spec, его источник и template
  ID через `StatementMappingDefaultResolver`;
- `dto.py` пока не разделён: файл мал, а физическое дробление не уменьшило бы
  сложность.

Пользовательское поведение, API payload и persistence-модели не изменены.

## Phase 3 — Repair layer direction

### Commit 3.1: domain control totals

Статус: completed 2026-07-28.

- `StatementControlTotals` и его стабильное JSON-представление перенесены в
  `domain/control_totals.py`;
- parsers, application workflows и validation используют domain type;
- `domain/validation.py` больше не зависит от parsing layer.

Пользовательское поведение и JSON payload контрольных итогов не изменены.

### Commit 3.2: deduplication ownership

Статус: completed 2026-07-28.

- fingerprint, решение о типе дубликата и чистая policy оставлены в
  `domain/deduplication.py`;
- DB lookup и изменение ORM-строк перенесены в
  `application/pipelines/deduplication.py`;
- application actor зависит от узкого `DuplicateLookup` protocol, а не от
  concrete repository;
- точный hash по-прежнему даёт `duplicate`, совпадение
  account/date/amount/currency — `possible_duplicate`.

Пользовательское поведение deduplication не изменено.

### Commit 3.3: document lifecycle policy

Статус: completed 2026-07-28.

- `UploadedDocumentStatus` перенесён из ORM-модуля в `domain/types.py`;
- разрешённые переходы статусов и вычисление статуса по состоянию
  `RawTransaction` собраны в `domain/document_lifecycle.py`;
- application workflows меняют статус документа через один transition helper;
- запрет reparse зафиксирован отсутствием переходов
  `failed_to_parse/imported -> parsed`;
- проверка связанных операций остаётся чистым domain predicate и защищает
  ignore/delete.

Отдельные State-классы для enum values не вводились. Пользовательское поведение
upload, review, ignore/delete и parse failure не изменено.

### Commit 3.4: mapping validation

Статус: completed 2026-07-28.

- `StatementMappingValidator.validate(...)` возвращает все найденные typed
  issues с `code`, `severity`, `message` и `fields`;
- preview и import используют один validation path;
- column/amount/control-total validation удалена из `reader.py` и собрана в
  `application/unknown_statement_mappings/validation.py`;
- API объединяет issues в один стабильный `mapping_validation_failed` response
  с ошибками для всех затронутых полей;
- validation tests собраны по владельцу поведения, дублирующие reader/helper
  tests удалены.

Validator оставлен в application mapping workflow: он проверяет
`StatementMappingSpec` и raw-table input, поэтому перенос в domain создал бы
обратную зависимость или преждевременный отдельный domain contract.

Exit: completed. Domain не импортирует repository, ORM или parser layer.

## Phase 4 — Split persistence

Статус: deferred 2026-07-28.

Разделение не выполняется только из-за размера `repository.py`. При текущем
наборе сценариев оно добавило бы новые файлы, wiring и временные compatibility
wrappers, не меняя транзакции, SQL или пользовательское поведение.

Вернуться к Phase 4 нужно, когда выполнено хотя бы одно условие:

- начинается фактическое выделение `import_review`;
- mapping, document lifecycle и review регулярно меняют persistence независимо;
- широкий repository заметно усложняет production use cases или их tests;
- одному persistence-направлению нужна отдельная оптимизация.

До этого `ImportRepository` и `ImportQueryRepository` остаются как есть. Не
создавать `BaseRepository`, generic CRUD или repository на каждую ORM-модель.
Планируемые границы сохранены ниже как ориентир, а не как текущая задача.

### Commit 4.1: document repository

Документы, attempts, raw creation и document status writes.

### Commit 4.2: mapping repository

Templates, executions и mapping idempotency.

### Commit 4.3: review repository

Review locks, duplicate/transfer lookup и row-operation linking.

### Commit 4.4: split query side

- document catalog/detail queries;
- review queue/evidence queries;
- отдельная узкая dashboard metrics projection при необходимости.

Отложенный exit: ни один repository не меняется одновременно из-за document
list, mapping и transfer workflow.

## Phase 5 — Simplify statement processing

### Commit 5.1: remove strategy wrappers

Статус: completed 2026-07-28.

- `StatementParseProcessor` делает одно явное ветвление через parser registry;
- known branch вызывает существующий `KnownStatementImportPipeline`;
- unknown branch вызывает существующий `UnknownStatementFallbackPipeline`;
- удалён весь `application/strategies/`: Protocol, resolver, context и две
  однооперационные wrapper-стратегии;
- новые processor-классы вместо удалённых wrappers не создавались.

Пользовательское поведение, parser metadata и порядок сохранения успешного
attempt не изменены.

### Commit 5.2: consolidate unknown analysis

Объединить только устойчивые группы:

- analysis models;
- column/table profiling;
- suggestion scoring;
- mapping contracts.

Не объединять bank parsers и не создавать generic plugin framework.

Exit: основной statement-processing flow читается сверху вниз без перехода
через пустые adapter layers.

## Phase 6 — Extract import review

### Commit 6.1: move pure review domain

Перенести classification, confirmability, lifecycle и queue. При необходимости
оставить временные compatibility imports на один commit.

### Commit 6.2: move review read side

Перенести read model, duplicate evidence и transfer suggestions.

### Commit 6.3: move mutation actors

Перенести lifecycle, confirmation, transfers, rules и undo.
`import_review` становится owner транзакции.

### Commit 6.4: migrate React API composition

API paths не меняются. Меняются только dependencies/imports.

### Commit 6.5: migrate chat

Chat использует те же application actors. Удаляются
`RawTransactionReviewer`/legacy review use case.

### Commit 6.6: remove ledger back-dependency

Ledger posting принимает posting facts/command и не обновляет import document
или review lifecycle.

Exit: API и chat используют один review feature; ledger не зависит от review
workflow.

## Phase 7 — Test and documentation cleanup

Следовать [`TEST_STRATEGY.md`](TEST_STRATEGY.md):

- удалить tests внутренних wrappers;
- объединить повторяющиеся API permission/error tests;
- разбить mega-files по capability;
- сохранить finance, workspace, idempotency и source-preservation tests;
- не менять matching semantics deduplication в этой фазе.

Обновить:

- `src/app/features/imports/README.md`;
- `src/app/features/ledger/README.md`;
- frontend cutover plan;
- этот index.

После завершения удалить этот roadmap или свернуть его в короткую запись:
активные docs не должны хранить завершённый migration log.

## Phase 8 — Deduplication hardening

Эта фаза выполняется последней и не блокирует структурный рефакторинг.

### Commit 8.1: overlapping statements characterization

- добавить сценарий выписок `1–15 июля` и `1–31 июля`;
- проверить междокументный `POSSIBLE_DUPLICATE`;
- проверить evidence предыдущего документа и ledger operation;
- не менять matching algorithm в characterization commit.

### Commit 8.2: separate duplicate signal from normalization error

- duplicate warning не хранится как неустранимая normalization error;
- `MARK_UNIQUE` действительно разрешает дальнейшее подтверждение;
- `MARK_DUPLICATE` остаётся terminal и не влияет на ledger.

### Commit 8.3: persistence race guards

- PostgreSQL test конкурентного confirmation;
- проверить достаточность confirmed dedupe constraint;
- изменить exact/fuzzy matching только по отдельному domain decision.

Exit: overlapping statements не удваивают деньги, а неоднозначные совпадения
требуют понятного решения пользователя.

## Проверки на каждой фазе

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest tests/features/imports tests/api/test_import_*.py
```

Для migration/concurrency commits дополнительно нужен PostgreSQL suite. React
cutover commits также требуют:

```bash
cd frontend
npm run lint
npm run typecheck
npm test
```
