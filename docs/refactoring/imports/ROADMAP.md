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
        preview.py
        importing.py
        templates.py
        contracts.py
        analysis.py

    domain/
      document_lifecycle.py
      statement_validation.py
      deduplication.py
      mapping_validation.py
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

- у `UnknownStatementMappingCommand` убран default `INCOME`;
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
  `UnknownStatementDraftMapper`, `preview_compatible_unknown_statement_mapping`
  и `compatible_mapping_tables`;
- удалены три теста, проверявшие только отсутствующий production workflow или
  однострочный forwarding adapter.

Public API и пользовательское поведение не изменены.

### Commit 2.2: deduplicate pure helpers

- review message append;
- typed integer decoding;
- latest-attempt selector;
- control-total decoder.

### Commit 2.3: document snapshot

- `ImportDocumentDetailView` → `ImportDocumentSnapshot`;
- удалить `ImportService`;
- repository возвращает bounded internal snapshot.

Exit: меньше слоёв без изменения API.

## Phase 3 — Repair layer direction

### Commit 3.1: domain control totals

Перенести `StatementControlTotals` в imports domain. Parsers используют domain
type.

### Commit 3.2: deduplication ownership

Оставить fingerprint/policy в domain; DB lookup и row orchestration перенести в
application.

### Commit 3.3: document lifecycle policy

Собрать status resolution и разрешённые transitions в одну чистую policy.
Не вводить отдельный State class для каждого enum value.

### Commit 3.4: mapping validation

Один validator возвращает issues с code, severity и fields. API преобразует
issues в typed response/errors.

Exit: domain не импортирует repository, ORM или parser layer.

## Phase 4 — Split persistence

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

Exit: ни один repository не меняется одновременно из-за document list,
mapping и transfer workflow.

## Phase 5 — Simplify statement processing

### Commit 5.1: replace strategy wrappers

`StatementProcessor` явно выбирает `KnownStatementProcessor` или
`UnknownStatementProcessor` через parser registry.

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
