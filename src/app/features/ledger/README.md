# Ledger module notes

`ledger` отвечает за учетный смысл денежных событий: операции, проводки,
ручные движения, импорты из банковских строк и внутренние переводы.

Главная цель модуля: финансовая корректность. Доходы и расходы меняют
финансовый результат, внутренние переводы меняют только место хранения денег.

## Product flow

```text
raw transaction review
-> Operation
-> MoneyEntry[]
-> account balance / reports

manual operation form
-> Operation
-> MoneyEntry[]
-> lifecycle actions: cancel / restore / delete
```

`Operation` описывает смысл события. `MoneyEntry` описывает движение по
конкретному счету. Перевод всегда должен балансироваться в ноль.

## Target architecture

Внутри feature держим такой поток:

```text
router.py
-> service facade / application use cases
-> domain rules and mapping helpers
-> repository.py
-> models.py
```

Router знает про HTTP, формы, redirects и шаблоны. Он не должен решать, как
собрать проводки или какие операции можно удалить.

Use case описывает пользовательское действие целиком: провести импортированную
строку, провести перевод, создать ручной расход, отменить ручную операцию.

Domain helpers должны оставаться чистыми: знаки сумм, балансировка переводов,
проверка статусов, восстановление статуса raw transaction после undo. Когда
правило создает доменный результат и держит его инварианты, предпочитаем
classmethod на value object: `TransferAmounts.for_manual_transfer(...)`,
`LedgerPostingPlan.from_raw_transaction(...)`. Свободные функции допустимы как
маленькие политики или совместимые обертки. Все это легко читать и тестировать
без БД. Если `domain/` начинает становиться ящиком для всего, правила надо
разносить в более точные файлы.

Repository содержит SQLAlchemy-запросы и persistence-действия. Тяжелые
read-side запросы для UI можно выделять в `*QueryRepository`, когда они начнут
мешать write-side коду.

DTO/ViewModel слой нужен для read-side UI, когда шаблоны начинают получать
слишком богатый ORM-граф. Для ledger предпочитаем однонаправленное
преобразование:

```text
Operation / MoneyEntry / Account ORM
-> LedgerViewMapper
-> *View dataclass
-> Jinja template
```

Обратный `DTO -> ORM` mapper пока не нужен. Write-side лучше держать через
явные command dataclasses, если формы или API-обработчики станут перегружены:

```text
Form / API input
-> *Command
-> *UseCase
-> Operation / MoneyEntry ORM
```

`schemas.py` откладываем до появления JSON API. Для SSR/Jinja текущие формы и
command dataclasses полезнее, чем внешние Pydantic response schemas.

## Naming guide

- `*UseCase` - пользовательский сценарий с транзакционными эффектами.
- `*Service` - временный фасад или тонкий application service.
- `*Repository` - persistence API поверх SQLAlchemy.
- `*Mapper` - однонаправленное преобразование ORM/read data в DTO/ViewModel.
- `*Command` - write-side намерение пользователя перед передачей в use case.
- `*Plan` - доменное решение до создания ORM-моделей.
- `*Amounts` - value object для пары или набора денежных сумм.
- `*Detail` / `*View` - данные для UI/read-side слоя.

## Current module map

- `router.py` - HTTP endpoints for manual operations.
- `service.py` - current facade for ledger workflows. Target: shrink over time.
- `application/commands.py` - write-side command dataclasses for ledger actions.
- `application/manual_operations.py` - manual income/expense/transfer lifecycle use case.
- `application/raw_transaction_posting.py` - imported raw transaction posting use case.
- `application/imported_operation_undo.py` - undo use case for imported bank PDF operations.
- `application/transfer_suggestions.py` - read-side use case for possible internal transfer matches.
- `application/ledger_reference_resolver.py` - account/category/property resolver with workspace checks.
- `application/imported_document_status.py` - imported document completion status helper.
- `domain/money.py` - pure money rules: signs, transfer amounts, currency checks.
- `domain/raw_transactions.py` - pure raw transaction posting rules and plans.
- `domain/text.py` - tiny text normalization helpers.
- `domain/__init__.py` - compatibility export for old imports from split domain helpers.
- `mapping/operation_factory.py` - ORM object builders for operations and money entries.
- `mapping/dto.py` - read-side DTOs and `LedgerViewMapper`.
- `errors.py` - ledger-specific application exceptions.
- `repository.py` - SQLAlchemy persistence and read queries.
- `models.py` - `Operation` and `MoneyEntry` persistence models.

## Package guide

Keep the root of `ledger/` small. New files should usually go into one of
these packages:

- `application/` - user workflows, orchestration, command handling, status updates.
- `domain/` - pure rules and value objects with no database/session dependency.
- `mapping/` - DTO projection and ORM object construction.

Avoid adding more one-off files at the root unless they are public module
entrypoints like `router.py`, `service.py`, `repository.py`, or `models.py`.

## Refactoring direction

Work in small behavior-preserving steps:

1. Keep tests green before and after each step.
2. Move pure domain rules out of services first.
3. Split manual operations from imported raw transaction posting.
4. Keep transfer logic explicit; never let transfers affect profit.
5. Preserve `LedgerPostingService` as a compatibility facade until routes and
   tests no longer need it.

## Near-term cleanup plan

1. Extract pure helpers and errors from `service.py`.
2. Extract manual operation use cases.
3. Extract imported raw transaction posting use cases.
4. Keep imported operation undo in its own use case.
5. Keep transfer suggestions in their own read-side use case.
6. Add read-side DTOs and `LedgerViewMapper` for account detail and manual
   operation pages.
7. Add more command dataclasses only when router form parsing becomes noisy.
8. Split broad domain helper files once they become harder to scan than their
   callers.
9. Add Pydantic schemas only when ledger gets a JSON API.

This note is intentionally small. If code and note disagree, fix the code or
update the note in the same change.
