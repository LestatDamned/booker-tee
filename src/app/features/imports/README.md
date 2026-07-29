# Imports module notes

`imports` отвечает за путь банковской выписки от загруженного файла до
проверяемых сырых транзакций и подготовленных действий пользователя.

Главная цель модуля: надежный, объяснимый и расширяемый импорт финансовых
данных. Магия допустима только там, где ее можно проверить и отменить.

## Product flow

```text
statement upload
-> UploadedDocument
-> ParseAttempt
-> extracted statement data
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

Внутри feature используем capability-first структуру с явными локальными
границами:

```text
API
-> documents commands / queries
-> statements process
   -> parsers для известного формата
   -> mapping для неизвестного формата
-> capability repository / storage
```

Это не отдельные фреймворки и не сложная абстракция ради абстракции. Это
просто способ разложить разные истории импорта:

- `documents` владеет upload, storage, parse attempts и document lifecycle;
- `statements` владеет созданием, валидацией и deduplication raw transactions;
- `parsers` распознаёт известные банковские форматы;
- `mapping` анализирует и импортирует неизвестные табличные форматы;
- `Parser` знает только банковскую грамматику конкретной выписки и возвращает drafts.
- `Repository` сохраняет ORM-модели и не принимает бизнес-решения.

```text
src/app/api/v1/imports router
-> documents command/query or mapping use case
-> statements workflow
-> parser/mapping policy
-> capability repository/storage
-> models.py
```

API router знает про HTTP schemas, dependencies и responses. Он не должен
содержать ветвление бизнес-сценариев вроде «как подтвердить строку». React
владеет browser presentation, а historical redirects находятся за пределами
feature в `src/app/legacy_frontend_redirects.py`.

Use case описывает пользовательское действие целиком: загрузить выписку,
обработать review-действие или удалить документ. Use case может координировать
несколько сервисов.

Внутренний workflow оформляется через именованный actor и предметное действие,
например `StatementParseCompletionService.complete_successful_attempt()` или
`KnownStatementImportPipeline.import_parsed_transactions()`. Название должно
объяснять результат без универсального `Processor.process()`.

Repository содержит SQLAlchemy-запросы и изменения ORM-моделей. Бизнес-решения
лучше держать выше, если они не являются простым persistence-действием.

Mapper/DTO превращает ORM-граф в данные для шаблона или внешнего слоя. Шаблоны
не должны вычислять бизнес-смысл из ORM-моделей.

Parser работает только с извлеченными данными выписки и возвращает
`RawTransactionDraft`. Этот контракт представлен `ExtractedStatement`, общим
value object для PDF/XLSX extracted text/tables. Парсер не создает ORM-модели,
не ходит в БД и не применяет категории.

## Story boundaries

`imports` содержит несколько разных историй. Их нельзя смешивать в одном файле
только потому, что все они называются "импорт".

### Document lifecycle

Отвечает за жизнь загруженного файла:

```text
statement upload
-> UploadedDocument
-> ParseAttempt
-> raw extracted text/tables
-> document status
```

Сюда относятся upload, storage, format-specific extraction, parse attempts и
ignore/delete.

Целевой пакет:

```text
documents/
  commands/
    upload.py
    manage.py
  queries/
    list.py
    detail.py
  attempts.py
  lifecycle.py
  repository.py
  storage.py
```

### Known statement import

Отвечает за выписки, которые распознаны конкретным банковским парсером:

```text
extracted statement data
-> parser registry
-> concrete bank parser
-> RawTransactionDraft[]
-> RawTransaction[]
-> validation/deduplication/review
```

Application workflow:

```text
statements/process.py
  StatementParseCompletionService.complete_successful_attempt()
  KnownStatementImportPipeline.import_parsed_transactions()
```

После Step 5C банковские реализации находятся рядом с parser contract и
registry:

```text
parsers/
  alfabank.py
  expobank.py
  ozon_bank.py
  sberbank.py
  tbank.py
  vtb/
    card.py
    deposit.py
    statement_period.py
```

Правило:

```text
parsers/protocol.py = canonical parser contract
parsers/registry.py = явный выбор подходящего parser
parsers/extractors/* = локальное извлечение PDF/XLSX
parsers/<bank>.py = один банковский формат
parsers/<bank>/* = несколько форматов одного банка
statements/process.py = что приложение делает с результатом парсера
```

### Unknown statement fallback

Отвечает за выписки без известного парсера:

```text
extracted statement data
-> unknown statement analysis
-> table previews / column profiles / mapping suggestions
-> user mapping or saved template
-> RawTransactionDraft[]
```

Целевые пакеты:

```text
application/unknown_statements/
  analyzer.py
  analysis_models.py
  hints.py
  value_detectors.py
  table_detection.py
  column_profiles.py
  mapping_suggestions.py
  table_analysis.py
  text_tables.py
  continuations.py
  control_totals.py
  fallback.py

application/unknown_statement_mappings/
  engine.py
  import_use_case.py
  template_use_case.py
  template_commands.py
  template_signatures.py
  mapping_defaults.py
  values.py
  raw_tables.py
  row_mapping.py
  drafts.py
```

### Import Review boundary

Жизнью `RawTransaction` после импорта управляет соседний feature
`app.features.import_review`:

```text
RawTransaction
-> needs_review / normalized / ignored / duplicate / confirmed
-> validation refresh
-> ledger posting
```

Review-слой не должен знать, каким способом строка попала в систему:
из известного парсера, из fallback mapping, или позже из другого канала.

## Target package map

Целевое "оглавление" модуля:

```text
imports/
  models.py
  errors.py

  documents/
    dto.py
    types.py
    errors.py
    lifecycle.py
    attempts.py
    validation_report.py
    storage.py
    repository.py
    commands/
      upload.py
      manage.py
    queries/
      list.py
      detail.py

  statements/
    dto.py
    types.py
    process.py
    raw_transactions.py
    deduplication.py
    validation.py
    validation_service.py
    repository.py

  application/
    unknown_statements/
      analyzer.py
      analysis_models.py
      hints.py
      value_detectors.py
      table_detection.py
      column_profiles.py
      mapping_suggestions.py
      table_analysis.py
      text_tables.py
      continuations.py
      control_totals.py
      fallback.py

    unknown_statement_mappings/
      engine.py
      import_use_case.py
      template_use_case.py
      template_commands.py
      template_signatures.py
      mapping_defaults.py
      values.py
      raw_tables.py
      row_mapping.py
      drafts.py

  mapping/
    repository.py

  parsers/
    protocol.py
    registry.py
    extractors/
      dto.py
      pdf.py
      xlsx.py
      resolver.py
    support/
      drafts.py
      headers.py
      normalization.py
    alfabank.py
    expobank.py
    ozon_bank.py
    sberbank.py
    tbank.py
    vtb/
      card.py
      deposit.py
      statement_period.py

import_review/
  application/
  domain/
  repository.py
```

This target map is a direction, not a required big-bang rewrite. Move files
only in behavior-preserving steps.

## Browser presentation boundary

Внутри `imports` больше нет SSR routes, Jinja presenters или ViewModels.
Активная browser-граница разделена явно:

```text
frontend/app/features/import-*  -> React presentation
src/app/api/v1/imports          -> versioned JSON API
src/app/legacy_frontend_redirects.py -> historical GET compatibility
```

Новые browser workflows не должны возвращать HTML из `imports`. Бизнес-правила
и transitions остаются в application/domain, API преобразует их в typed DTO,
а React владеет visual copy и view state.

## Sensitive local fixtures

Some files under `tests/fixtures/` are real or otherwise sensitive bank
statements used only for local manual verification. They must not be committed,
uploaded to external services, pasted into chats, or used as shared test data.
They may be used locally to understand parser behavior and write code, as long
as private values never leave the local workspace.

Current local sensitive fixture examples:

```text
tests/fixtures/alfa_bank_card_statement.xlsx
tests/fixtures/ozonbank_card_statement.pdf
tests/fixtures/t_bank_card_statement.pdf
```

The repository `.gitignore` intentionally ignores `tests/fixtures/*` except
sanitized unknown-statement JSON fixtures under `tests/fixtures/unknown_statements/`.
If a real PDF/XLSX fixture appears in `git status`, stop and fix ignore rules
before committing.

Committed tests should use sanitized extracted-data fixtures or generated
minimal files that contain no real names, account numbers, card numbers,
addresses, transaction descriptions, document IDs, or balances from private
statements.

When a real fixture is needed to understand a bank layout, extract only the
structural facts into code/docs:

- stable public bank markers;
- non-private column headers;
- date, amount, currency, debit/credit, balance, and totals shape;
- whether a format is PDF, XLSX, or another file type.

Do not copy private row values into tests, logs, README examples, parser error
messages, or issue descriptions.

Allowed local use:

- inspect the file locally while implementing an extractor or parser;
- run local parser tests or one-off local checks against the private fixture;
- derive sanitized fixtures from its structure, after replacing all private
  values with fake data.

Not allowed:

- committing the original file or private extracted rows;
- pasting real rows, names, account numbers, card numbers, document IDs,
  balances, or descriptions into source files, docs, logs, prompts, or issues;
- sending the file or extracted contents to external AI/API services unless the
  user explicitly asks for that specific action.

## Planned Ozon, T-Bank, and Alfa support

Near-term target: add support for Ozon Bank, T-Bank, and Alfa Bank statements
without widening the MVP beyond reliable import and review.

Implementation direction:

1. Build dedicated known parsers first for the three local statement layouts.
2. Use the format-aware extraction layer for `.pdf` and `.xlsx`; Alfa statements
   may arrive as `.xlsx` instead of PDF.
3. Use the private files under `tests/fixtures/` only as local reference input;
   commit sanitized extracted-data fixtures or generated minimal files instead.
4. Preserve raw payloads, stable source row ids, and dedupe hashes.
5. Preserve control totals where available and mark mismatches for review.
6. Keep all imported rows reviewable; do not auto-confirm accounting records
   directly from these parsers.
7. Improve the unknown importer afterwards, using lessons from the dedicated
   parsers.

Dedicated parser order:

1. `parsers/alfabank.py` - table-like XLSX with statement preamble.
2. `parsers/ozon_bank.py` - PDF tables with operation rows.
3. `parsers/tbank.py` - text-layout PDF; likely the most fragile.

The first useful vertical slice for Alfa XLSX is:

```text
.xlsx upload
-> local storage
-> OpenPyXL extraction into common extracted statement shape
-> dedicated Alfa XLSX parser
-> RawTransactionDraft rows
-> validation/deduplication/review
```

Dedicated parser targets:

```text
parsers/alfabank.py
parsers/ozon_bank.py
parsers/tbank.py
```

If T-Bank card and deposit statements have materially different layouts, split
the current `tbank.py` into `tbank/card.py` and `tbank/deposit.py`.

The unknown importer remains important as a fallback and future generic table
importer, but it is not the primary path for these three known formats while
the dedicated parser work is in progress.

## Parser package direction

`parsers/` is the single capability package for statement recognition. Its
root contains the explicit parser contract, registry and bank implementations;
file extraction and shared pure helpers live in named subpackages:

```text
parsers/
  protocol.py
  registry.py
  extractors/
    dto.py
    resolver.py
    pdf.py
    xlsx.py
  support/
    drafts.py
    headers.py
    normalization.py
  alfabank.py
  expobank.py
  ozon_bank.py
  sberbank.py
  tbank.py
  vtb/
    card.py
    deposit.py
    statement_period.py
```

Use a bank folder only when the bank has several statement formats or shared
bank-specific code. Keep a single-format bank parser in one file. Split a
parser further only when the file stops reading linearly:

```text
parsers/tbank/card/
  parser.py
  rows.py
  totals.py
```

Avoid introducing a base parser class or inheritance tree until there is a
clear repeated algorithm that a small helper function cannot handle. The current
`BankStatementParser` `Protocol` is the preferred extension point:
plain dataclasses, pure helpers, and explicit parser registration keep the
import path easy to test.

## Naming guide

- `*UseCase` - пользовательский сценарий или action с транзакционными эффектами.
- `*Service` / `*Pipeline` - внутренний workflow; имя actor должно объяснять,
  какой результат он создаёт или какой этап завершает.
- `*Mapper` - преобразование между ORM, DTO, drafts и view models.
- `*Draft` - данные, которые еще не являются ORM-моделью.
- `*View` / `*ViewModel` - данные, подготовленные для Jinja-шаблона.
- `*Repository` - persistence API поверх SQLAlchemy.
- `*QueryRepository` - read-side запросы с тяжелыми `selectinload` и view needs.

## Current module map

- `../import_review/application/` - Import Review read model, classification,
  duplicate evidence, transfer options, transfer candidate matching and typed
  mutation services for confirmation, lifecycle, transfers, rules and undo.
- `documents/` - document commands, DTO, list/detail queries, repository,
  lifecycle, parse attempts, storage, errors and the typed stored validation
  report contract. Repository snapshots decode that JSONB contract once before
  application readers receive it.
- `statements/process.py` - parse completion and known parser import workflows
  with explicit `Class.action` APIs.
- `statements/dto.py`, `types.py`, `raw_transactions.py` - shared parser/mapping
  result, row status and `RawTransactionMapper`.
- `statements/deduplication.py` - duplicate policy and persistence-aware
  `RawTransactionDeduplicator`.
- `statements/validation.py`, `validation_service.py` - pure validation and
  document/attempt persistence orchestration.
- `statements/repository.py` - raw row creation, dedupe lookups and
  superseding.
- `application/unknown_statements/` - unknown statement fallback and analysis internals: fallback/template pipeline, hints, DTOs, table detection, column profiles, profile helpers, suggestions, suggestion scoring, continuations, and control totals.
- `application/unknown_statement_mappings/` - unknown statement mapping workflows
  and internals: mapping engine, idempotent import use case, template use case,
  template matching, table signatures, typed stored-report defaults, typed
  command validation, DTOs, raw table navigation, row mapping, and draft
  conversion.
- `documents/lifecycle.py` - document status transition matrix, review status
  resolution and linked-operation predicate.
- `documents/queries/detail.py` и `/api/v1/imports/documents/{id}`
  владеют безопасной typed projection React document detail; technical storage
  paths и полный raw payload в browser DTO не входят.
- `errors.py` - temporary shared mapping/review exceptions until their owning
  capabilities move.
- `mapping/repository.py` - mapping templates and execution persistence pending
  the full mapping move.
- `documents/storage.py` - local upload storage.
- `parsers/extractors/` - extraction DTO, resolver and local PDF/XLSX adapters.
- `parsers/protocol.py` - canonical parser protocol; shared result values live in
  `statements/dto.py`.
- `parsers/registry.py` - parser registry for known statement parsers.
- `parsers/support/` - named draft-building, header-recognition and normalization
  helpers shared by known parsers and unknown-statement mapping.
- `parsers/*.py` - single-format bank parser plugins.
- `parsers/vtb/` - related VTB card/deposit parsers and statement-period helper.

## Imports UI geometry

The stabilized import review screen is the visual reference for the imports
flow. Other imports pages may have different content, but should reuse the same
geometry where the concept matches:

- context/status/financial facts on the left;
- primary action or next step in a predictable action area;
- money, date, status, and badges in stable positions;
- row lists shaped like close relatives of review rows;
- technical/debug details collapsed and visually secondary.

Document detail is an overview page, not a full review screen, so it can be
more compact. Mapping is a setup page, so it can use form/table geometry. Both
should still feel like they belong to the same import workflow rather than a
separate screen family.

## Import style

Prefer explicit imports from concrete modules over package-level re-export
barrels. For example, import upload validation from
`documents/commands/upload.py`, the pure deduplication policy from
`statements/deduplication.py`, and concrete bank parsers from their parser
modules.

Do not use broad `__all__` barrels as the normal import style inside this
feature. A reader should be able to understand ownership from the import path.

Prefer:

```python
from app.features.imports.application.unknown_statements.analyzer import (
    analyze_unknown_statement,
)
from app.features.imports.mapping.rows import map_table_rows
```

Avoid creating new broad facade modules:

```python
from app.features.imports.application.some_unknown_statement_facade import (
    analyze_unknown_statement,
    map_table_rows,
)
```

Внутренние file moves не сохраняют compatibility facade: все consumers
переводятся на defining module в одном change set.

## Package guide

Keep the root of `imports/` small. New files belong to the capability that owns
their reason to change:

- `documents/` - commands, queries, lifecycle, storage and document persistence;
- `statements/` - raw transaction workflow, validation, deduplication and
  statement persistence;
- `parsers/` - parser protocol, registry, extractors, shared pure support and
  known bank implementations;
- `mapping/` - unknown-format analysis, templates, commands, queries and
  persistence as it moves from the temporary `application/unknown_*` packages.

Root files are reserved for the shared ORM aggregate and truly cross-capability
errors. Do not recreate `domain/`, `infrastructure/`, `parsing/` or generic
`service.py`/`query_repository.py` entrypoints.

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
builder = StatementMappingDraftBuilder(spec=spec, account_id=account_id)
drafts = builder.build_rows(mapped_rows)
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

1. Keep document reads on internal snapshots returned by
   `documents.repository.DocumentRepository`; command routes call explicit use
   cases directly.
2. Keep document commands, storage, lifecycle and persistence inside the
   completed `documents` capability.
3. Keep review lifecycle and user actions in the sibling `import_review`
   feature; imports retains document validation and persistence.
4. Keep `StatementParseCompletionService.complete_successful_attempt()` as the
   explicit parse-success workflow: store extracted data, select known parser
   or unknown fallback, then delegate to the named pipeline action.
5. Add dedicated Alfa XLSX parser.
6. Add dedicated Ozon Bank card PDF parser.
7. Add dedicated T-Bank card parser or a narrowly scoped text-layout parser.
8. Fold proven generic improvements back into the unknown importer after the
   dedicated parsers are stable.
9. Avoid adding new compatibility facades for application commands.

Completed cleanup:

- Canonical parser contract and registry live in `parsers/protocol.py` and
  `parsers/registry.py`.
- Statement extraction DTO, resolver and PDF/XLSX adapters live in
  `parsers/extractors/`.
- Parser selection and parsing use explicit actor actions:
  `StatementParserRegistry.find_matching_parser()` and
  `BankStatementParser.parse_transaction_drafts()`.
- Extraction compatibility aliases and old `infrastructure/extraction/`,
  `parsing/parser_types.py` and `parsing/registry.py` paths are removed.

Parser support cleanup completed in Step 5B:

- Shared helpers live in `parsers/support/drafts.py`, `headers.py` and
  `normalization.py`; the old `parsing/support/` path is removed.
- Call sites use explicit names such as `extracted_statement_text()`,
  `row_cell()` and `parse_or_record_error()`.

Bank parser cleanup completed in Step 5C:

- Single-format bank implementations live directly in `parsers/*.py`.
- VTB remains a package because card and deposit formats share period parsing.
- Five empty bank package files were removed without compatibility re-exports.

Step 5D cleanup completed:

- The empty historical `parsing/` package is removed.
- No old parser imports, facades or re-exports remain.
- `parsers` depends only on extracted DTO, statement DTO/types and pure local
  support; it does not import FastAPI, SQLAlchemy, ORM or application modules.

## Remaining cleanup plan

1. Keep document read projections in `documents/repository.py`; new command
   behavior belongs to explicit use cases under `documents/commands/`.
2. Compatibility facades in `application/` have been removed. Keep new imports
   pointed at concrete story modules such as `documents/commands/upload.py`
   or the defining module under `app.features.import_review`.
3. Keep import tests split by story:
   bank parsers, validation, unknown statement analysis, and unknown mapping
   now live in separate files. The remaining `test_imports.py` covers small
   upload, document, deduplication, and review utility scenarios.
4. Make the top-level import story explicit in code:
   upload, extract, choose strategy, parse/map, store raw rows, validate,
   then review.

## Document read boundary

`DocumentRepository.get_document_snapshot(...)` owns workspace-scoped loading
and returns `ImportDocumentSnapshot`. Document detail and unknown mapping
readers depend on narrow Protocols and do not receive ORM documents. Command
workflows remain explicit application use cases.
