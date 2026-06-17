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

Внутри feature используем вертикальный slice, но держим явные границы:

```text
router.py
-> use cases / service facade
-> processors and domain helpers
-> repository.py / storage.py
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
result.

Repository содержит SQLAlchemy-запросы и изменения ORM-моделей. Бизнес-решения
лучше держать выше, если они не являются простым persistence-действием.

Mapper/DTO превращает ORM-граф в данные для шаблона или внешнего слоя. Шаблоны
не должны вычислять бизнес-смысл из ORM-моделей.

Parser работает только с `ExtractedPdf` и возвращает `RawTransactionDraft`.
Парсер не создает ORM-модели, не ходит в БД и не применяет категории.

## Naming guide

- `*UseCase` - пользовательский сценарий или action с транзакционными эффектами.
- `*Processor` - внутренний pipeline из нескольких шагов без HTTP-контекста.
- `*Mapper` - преобразование между ORM, DTO, drafts и view models.
- `*Draft` - данные, которые еще не являются ORM-моделью.
- `*View` / `*ViewModel` - данные, подготовленные для Jinja-шаблона.
- `*Repository` - persistence API поверх SQLAlchemy.
- `*QueryRepository` - read-side запросы с тяжелыми `selectinload` и view needs.

## Current module map

- `router.py` - HTTP endpoints for upload, document detail, review actions.
- `service.py` - current facade for import workflows. Target: shrink over time.
- `review.py` - review action use case for raw transaction confirmation/status.
- `review_status.py` - status-only raw transaction review actions.
- `statement_upload.py` - statement upload and first parse use case.
- `document_management.py` - document ignore/delete use case.
- `statement_reparse.py` - statement reparse use case.
- `processing.py` - parse success pipeline. Target: split into smaller helpers.
- `parse_attempts.py` - shared helpers for parser attempts and parser errors.
- `deduplication.py` - duplicate detection for imported raw transactions.
- `raw_transaction_mapper.py` - `RawTransactionDraft` to ORM model mapping.
- `errors.py` - import-specific application exceptions.
- `validation.py` - pure statement total validation logic.
- `dto.py` - import detail view models and mapper.
- `repository.py` - SQLAlchemy persistence and compatibility read wrappers.
- `query_repository.py` - read-side document queries for UI/detail workflows.
- `storage.py` - local upload storage.
- `parser_types.py` - parser contracts and parser-facing value objects.
- `extraction/` - PDF extraction adapters.
- `parsers/` - bank and statement-type parsers.

## Refactoring direction

Work in small behavior-preserving steps:

1. Keep tests green before and after each step.
2. Move one responsibility at a time.
3. Prefer plain dataclasses, pure functions, and Protocols when they reduce
   coupling.
4. Avoid speculative abstractions until at least two real use cases need them.
5. Keep parser files shaped like a story:

```text
markers / regexes
-> raw row dataclasses
-> parser class
-> extract rows
-> parse row
-> build draft
-> totals and small helpers
```

## Near-term cleanup plan

1. Turn `ImportService` into a small facade over explicit use cases.

## Deferred cleanup

`ImportService` intentionally remains as a compatibility facade for routers and
tests. Most business workflows already live in explicit use cases, so removing
the facade is not urgent.

Prefer direct router-to-use-case wiring only when:

1. A route clearly belongs to one use case.
2. The facade starts hiding important workflow boundaries.
3. Backward-compatible imports from `service.py` are no longer useful for tests.

This note is intentionally small. If code and note disagree, fix the code or
update the note in the same change.
