# Imports module notes

`imports` отвечает за путь банковской выписки от загруженного PDF до
проверяемых сырых транзакций и подготовленных действий пользователя.

Главная цель модуля: надежный, объяснимый и расширяемый импорт финансовых
данных. Магия допустима только там, где ее можно проверить и отменить.

## Product flow

```text
PDF upload
-> UploadedDocument
-> ParseAttempt
-> ExtractedPdf
-> parser registry
-> RawTransactionDraft[]
-> RawTransaction[]
-> deduplication
-> transaction rule suggestions
-> statement validation
-> review screen
-> ledger posting
```

Сырой импорт должен сохраняться даже при ошибке парсинга. Подтвержденные
проводки создаются только после review/action слоя, а не напрямую из парсера.

## Target architecture

Внутри feature используем вертикальный slice, но держим явные границы.
Архитектурная форма модуля:

```text
Use Case / Facade
-> Pipeline
-> Strategy
-> Parser / Mapping / Domain rules
-> Repository / Infrastructure
```

Это не отдельные фреймворки и не сложная абстракция ради абстракции. Это
просто способ разложить разные истории импорта:

- `UseCase` описывает пользовательское действие: загрузить, перепарсить,
  применить маппинг, изменить review-статус.
- `Pipeline` описывает последовательность шагов внутри импорта: сохранить
  документ, извлечь PDF, выбрать путь обработки, создать raw rows, проверить,
  дедуплицировать, отправить на review.
- `Strategy` выбирает способ обработки выписки: известный банковский парсер,
  сохраненный шаблон неизвестной выписки, ручной mapping/fallback.
- `Parser` знает только банковскую грамматику PDF и возвращает drafts.
- `Repository` сохраняет ORM-модели и не принимает бизнес-решения.

```text
router.py
-> use cases / service facade
-> application pipelines / strategies / use cases
-> domain rules / mapping / parsing / infrastructure
-> repository.py / query_repository.py / storage.py
-> models.py
```

Роутер знает про HTTP, формы, шаблоны и redirects. Он не должен содержать
ветвление бизнес-сценариев вроде "как подтвердить строку" или "как перепарсить
документ".

Use case описывает пользовательское действие целиком: загрузить выписку,
перепарсить документ, обработать review-действие, удалить документ. Use case
может координировать несколько сервисов.

Processor выполняет внутренний pipeline без знания про HTTP: преобразовать
результат парсинга в raw transactions, отметить дубли, сохранить validation
result. В коде такие pipeline-части живут в `application/`, потому что они
оркестрируют сохранение и статусы, а не являются чистыми доменными правилами.

Repository содержит SQLAlchemy-запросы и изменения ORM-моделей. Бизнес-решения
лучше держать выше, если они не являются простым persistence-действием.

Mapper/DTO превращает ORM-граф в данные для шаблона или внешнего слоя. Шаблоны
не должны вычислять бизнес-смысл из ORM-моделей.

Parser работает только с `ExtractedPdf` и возвращает `RawTransactionDraft`.
Парсер не создает ORM-модели, не ходит в БД и не применяет категории.

## Story boundaries

`imports` содержит несколько разных историй. Их нельзя смешивать в одном файле
только потому, что все они называются "импорт".

### Document lifecycle

Отвечает за жизнь загруженного файла:

```text
PDF upload
-> UploadedDocument
-> ParseAttempt
-> raw extracted text/tables
-> document status
```

Сюда относятся upload, storage, parse attempts, reparse, ignore/delete.

Целевой пакет:

```text
application/documents/
  upload.py
  reparse.py
  management.py
  parse_attempts.py
```

### Known statement import

Отвечает за выписки, которые распознаны конкретным банковским парсером:

```text
ExtractedPdf
-> parser registry
-> concrete bank parser
-> RawTransactionDraft[]
-> RawTransaction[]
-> validation/deduplication/review
```

Целевой пакет:

```text
application/known_statements/
  pipeline.py
  strategy.py
```

Банковские парсеры остаются в нижнем слое:

```text
parsing/parsers/
  expobank.py
  sberbank_card.py
  vtb_card.py
  vtb_deposit.py
```

Правило:

```text
parsing/parsers/* = как прочитать конкретный формат PDF
application/known_statements/* = что приложение делает с результатом парсера
```

### Unknown statement fallback

Отвечает за выписки без известного парсера:

```text
ExtractedPdf
-> unknown statement analysis
-> table previews / column profiles / mapping suggestions
-> user mapping or saved template
-> RawTransactionDraft[]
```

Целевые пакеты:

```text
application/unknown_statements/
  analyzer.py
  analysis_dto.py
  column_dto.py
  suggestion_dto.py
  table_preview_dto.py
  dto.py
  hints.py
  header_keywords.py
  value_detectors.py
  row_detection.py
  heuristics.py
  table_detection.py
  column_profiles.py
  profile_helpers.py
  mapping_suggestions.py
  suggestion_scoring.py
  continuations.py
  control_totals.py

application/unknown_statement_mappings/
  preview.py
  import_use_case.py
  template_use_case.py
  form_commands.py
  template_commands.py
  template_signatures.py
  ui_defaults.py
  values.py
  raw_tables.py
  row_mapping.py
  drafts.py
  templates.py
```

### Review lifecycle

Отвечает за жизнь `RawTransaction` после импорта:

```text
RawTransaction
-> needs_review / normalized / ignored / duplicate / confirmed
-> validation refresh
-> ledger posting
```

Целевой пакет:

```text
application/review/
  actions.py
  status.py
  validation_refresh.py
```

Review-слой не должен знать, каким способом строка попала в систему:
из известного парсера, из fallback mapping, или позже из другого канала.

## Target package map

Целевое "оглавление" модуля:

```text
imports/
  router.py
  service.py
  repository.py
  query_repository.py
  models.py
  errors.py

  routes/
    documents.py
    mapping.py
    review.py
    form_values.py

  application/
    documents/
      upload.py
      reparse.py
      management.py
      parse_attempts.py

    pipelines/
      statement_import.py
      context.py
      steps.py

    strategies/
      resolver.py
      known_parser.py
      unknown_fallback.py
      context.py

    known_statements/
      pipeline.py
      strategy.py

    unknown_statements/
      analyzer.py
      analysis_dto.py
      column_dto.py
      suggestion_dto.py
      table_preview_dto.py
      dto.py
      hints.py
      header_keywords.py
      value_detectors.py
      row_detection.py
      heuristics.py
      table_detection.py
      column_profiles.py
      profile_helpers.py
      mapping_suggestions.py
      suggestion_scoring.py
      continuations.py
      control_totals.py

    unknown_statement_mappings/
      preview.py
      import_use_case.py
      template_use_case.py
      form_commands.py
      template_commands.py
      template_signatures.py
      ui_defaults.py
      values.py
      raw_tables.py
      row_mapping.py
      drafts.py
      templates.py

    review/
      actions.py
      status.py
      validation_refresh.py

  domain/
    deduplication.py
    validation.py

  mapping/
    dto.py
    raw_transaction_mapper.py

  infrastructure/
    storage.py
    extraction/
      pdfplumber_extractor.py

  parsing/
    parser_types.py
    parsers/
      factory.py
      common.py
      normalization.py
      expobank.py
      sberbank_card.py
      vtb_card.py
      vtb_deposit.py
      vtb_shared.py
```

This target map is a direction, not a required big-bang rewrite. Move files
only in behavior-preserving steps.

## Naming guide

- `*UseCase` - пользовательский сценарий или action с транзакционными эффектами.
- `*Processor` - внутренний pipeline из нескольких шагов без HTTP-контекста.
- `*Mapper` - преобразование между ORM, DTO, drafts и view models.
- `*Draft` - данные, которые еще не являются ORM-моделью.
- `*View` / `*ViewModel` - данные, подготовленные для Jinja-шаблона.
- `*Repository` - persistence API поверх SQLAlchemy.
- `*QueryRepository` - read-side запросы с тяжелыми `selectinload` и view needs.

## Current module map

- `router.py` - thin HTTP router aggregator for the imports feature.
- `routes/` - story-based HTTP endpoints: documents/upload lifecycle,
  unknown statement mapping, and review actions.
- `service.py` - small read-side facade for document list/detail views.
- `application/documents/` - document lifecycle use cases and helpers: upload, reparse, ignore/delete, parse attempts.
- `application/review/` - review lifecycle use cases and helpers: confirmation/transfer actions, status changes, validation refresh.
- `application/processing.py` - parse success orchestrator: stores extracted PDF data, resolves an import strategy, then runs it.
- `application/strategies/` - import strategy resolver and branches for known parser imports and unknown statement fallback.
- `application/pipelines/` - shared import pipeline steps: review-required attempts and validation result storage.
- `application/known_statements/` - known bank parser pipeline: drafts, raw rows, deduplication, rules, validation.
- `application/unknown_statements/` - unknown statement fallback and analysis internals: fallback/template pipeline, hints, DTOs, table detection, column profiles, profile helpers, suggestions, suggestion scoring, continuations, and control totals.
- `application/unknown_statement_mappings/` - unknown statement mapping workflows and internals: preview, import use case, template use case, form command parsing, template matching, table signatures, UI defaults, commands/DTOs, raw table navigation, row mapping, and draft conversion.
- `domain/deduplication.py` - duplicate detection for imported raw transactions.
- `domain/validation.py` - pure statement total validation logic.
- `mapping/raw_transaction_mapper.py` - `RawTransactionDraft` to ORM model mapping.
- `mapping/dto.py` - import detail view models and mapper.
- `presentation/` - small view/page-context helpers for routers/templates:
  document/upload contexts, redirect anchors, selected mapping table, form
  reference parsing, review context, and validation messages.
- `errors.py` - import-specific application exceptions.
- `repository.py` - SQLAlchemy persistence and compatibility read wrappers.
- `query_repository.py` - read-side document queries for UI/detail workflows.
- `infrastructure/storage.py` - local upload storage.
- `infrastructure/extraction/` - PDF extraction adapters.
- `parsing/parser_types.py` - parser contracts and parser-facing value objects.
- `parsing/parsers/` - bank and statement-type parsers.

## Import style

Prefer explicit imports from concrete modules over package-level re-export
barrels. For example, import upload validation from
`application/documents/upload.py`, deduplication rules from
`domain/deduplication.py`, and concrete bank parsers from their parser modules.

Do not use broad `__all__` barrels as the normal import style inside this
feature. A reader should be able to understand ownership from the import path.

Prefer:

```python
from app.features.imports.application.unknown_statements.analyzer import (
    analyze_unknown_statement,
)
from app.features.imports.application.unknown_statement_mappings.row_mapping import (
    map_table_rows,
)
```

Avoid creating new broad facade modules:

```python
from app.features.imports.application.some_unknown_statement_facade import (
    analyze_unknown_statement,
    map_table_rows,
)
```

Compatibility facade files are allowed only as temporary migration shims for
old imports. Do not turn facade files into public "everything exports" modules.
When a facade is no longer needed by existing callers, remove it instead of
expanding it.

## Package guide

Keep the root of `imports/` small. New files should usually go into one of
these packages:

- `application/` - user workflows, parser attempts, review actions, upload and reparse orchestration.
- `application/<workflow_package>/` - cohesive helpers for one application workflow when a single file stops reading linearly.
- `domain/` - pure import rules such as deduplication and statement total validation.
- `mapping/` - DTO projection and draft-to-ORM mapping.
- `presentation/` - HTTP/template-facing helpers that prepare display values
  but do not perform business workflow decisions.
- `routes/` - FastAPI route modules grouped by user story. Keep them thin:
  request parsing, dependency injection, response rendering, redirects, and
  HTTP errors.
- `infrastructure/` - filesystem/PDF extraction adapters and other I/O details.
- `parsing/` - parser contracts, registry, normalization, and bank-specific parsers.

Avoid adding more one-off files at the root unless they are public module
entrypoints like `router.py`, `service.py`, `repository.py`, `query_repository.py`,
or `models.py`.

## DTOs and mappers

DTO/value objects may have methods for behavior that belongs to the object
itself:

```python
row.is_valid()
row.has_error()
row.display_status()
```

Do not make DTOs responsible for converting themselves into objects from the
next pipeline layer when that conversion needs outside context such as
`account_id`, mapping command, dedupe hash, raw payload contract, repository
state, or parser/import status.

Prefer mapper objects for cross-layer transformations:

```python
mapper = UnknownStatementDraftMapper(command=command, account_id=account_id)
drafts = mapper.map_rows(mapped_rows)
```

This keeps DTOs small and still gives the code a readable `Class.action()`
shape.

## Refactoring direction

Work in small behavior-preserving steps:

1. Keep tests green before and after each step.
2. Move one responsibility at a time.
3. Prefer plain dataclasses, pure functions, and Protocols when they reduce
   coupling.
4. Avoid speculative abstractions until at least two real use cases need them.
5. Keep package boundaries visible: application orchestrates, domain decides,
   mapping translates, infrastructure talks to I/O, parsing reads bank data.
6. Keep parser files shaped like a story:

```text
markers / regexes
-> raw row dataclasses
-> parser class
-> extract rows
-> parse row
-> build draft
-> totals and small helpers
```

Unknown statement importer files should follow the same story shape:

```text
facade / use case
-> DTOs and commands
-> raw input navigation
-> row/table analysis
-> mapping or draft conversion
-> validation/storage side effects
```

The old broad unknown-statement facade files were removed. Put new
implementation details into the cohesive packages underneath
`application/unknown_statements/` and `application/unknown_statement_mappings/`.

## Near-term cleanup plan

1. Keep `ImportService` as a read-side facade only; command routes should call
   explicit use cases directly.
2. Move document lifecycle files into `application/documents/`:
   upload, reparse, management, parse attempts.
3. Move review lifecycle files into `application/review/`:
   review actions, status changes, validation refresh.
4. Keep `application/processing.py` as a thin parse-success story:
   store extracted PDF data, resolve strategy, then run known parser or unknown
   fallback.
5. Keep bank-specific parser files inside `parsing/parsers/`.
6. Avoid adding new compatibility facades for application commands.

## Remaining cleanup plan

1. Keep slimming `router.py`:
   move repeated template context building into `presentation/`, then split
   routes by story only when the single router stops being useful.
2. Keep `ImportService` read-side:
   it may list documents and build detail views, but new command behavior
   should go into explicit use cases under `application/`.
3. Compatibility facades in `application/` have been removed. Keep new imports
   pointed at concrete story modules such as `application/documents/upload.py`
   and `application/review/status.py`.
4. Keep import tests split by story:
   bank parsers, validation, unknown statement analysis, and unknown mapping
   now live in separate files. The remaining `test_imports.py` covers small
   upload, document, deduplication, and review utility scenarios.
5. Make the top-level import story explicit in code:
   upload, extract, choose strategy, parse/map, store raw rows, validate,
   then review.

## Deferred cleanup

`ImportService` intentionally remains as a read-side facade for routes and
tests. Command workflows should be wired directly from routes to use cases.

Prefer direct router-to-use-case wiring only when:

1. A route clearly belongs to one use case.
2. The route performs a state-changing command.
3. The facade would hide important workflow boundaries.

This note is intentionally small. If code and note disagree, fix the code or
update the note in the same change.
