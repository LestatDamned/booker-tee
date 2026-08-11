# Ledger

`ledger` отвечает за подтверждённый финансовый смысл денежных событий:
`Operation`, связанные `MoneyEntry`, ручные операции, проведение импортированных
строк и внутренние переводы.

Главный приоритет — финансовая корректность:

- income и expense влияют на финансовый результат;
- transfer меняет только место хранения денег и всегда имеет
  `affects_profit=false`;
- transfer entries балансируются в ноль;
- все обращения к финансовым данным ограничены workspace;
- raw import row не превращается в подтверждённую операцию вне application
  workflow;
- review-поля импортированной операции исправляются только в статусе
  `confirmed` и с проверкой ожидаемой версии;
- lifecycle импортированной операции не меняется через correction form:
  отмена posting выполняется отдельным undo workflow;
- несколько записей одного workflow фиксируются атомарно.

## Основные потоки

```text
manual command API / chat
  -> ManualOperationService / ManualOperationWriter
  -> LedgerRepository
  -> Operation + MoneyEntry[]

operations API
  -> OperationsReader
  -> LedgerRepository
  -> unified workspace-scoped read model

raw transaction review
  -> ImportReviewConfirmationActor / ImportReviewTransferActor
  -> validate and link raw rows in import_review
  -> LedgerPostingService
  -> LedgerRepository
  -> Operation + MoneyEntry[]

account legacy screen
  -> AccountLedgerReader
  -> LedgerRepository
  -> account ledger read model
```

Manual command schemas находятся в `app/api/v1/manual_ledger`, canonical list
schemas — в `app/api/v1/operations`. Ledger application layer
не импортирует FastAPI/Pydantic API models и возвращает собственные immutable
Pydantic contracts.

## Структура

```text
ledger/
  application/
    account_ledger.py          # legacy account read model and reader
    imported_operations.py     # imported operation review edits and correction
    ledger_reference_resolver.py
    manual_mutations.py        # manual write workflows
    manual_operations.py       # public manual service and reference reader
    operations.py              # unified operation reader and source-aware projection
    posting.py                 # ledger writes from validated financial facts

  schemas/
    listing.py                 # pagination and query filters
    manual.py                  # manual commands, read DTOs and reference options
    operations.py              # unified DTO, provenance and capabilities

  domain/
    manual_idempotency.py      # stable identity of manual write intentions
    money.py                   # signs, amounts, currency and balance rules
    text.py                    # shared ledger text normalization
    types.py                   # operation enums and lifecycle/action policies

  mapping/
    manual_read.py             # semantic manual operation read projection
    records.py                 # ledger ORM record factory

  errors.py
  models.py
  repository.py
```

Папки отражают реальные границы, но новый файл не создаётся только ради одного
класса. Несколько небольших actors одной истории могут жить в одном модуле.

## Ответственности

### Application

Application actors оркестрируют workflow и разрешают workspace-scoped references.
Публичная transactional shell владеет commit/rollback всего пользовательского
сценария; вложенные writers, reviewers и posters только изменяют session и делают
flush. Они могут использовать SQLAlchemy session и repositories, но не знают про
HTTP, templates и API schemas.

Public actors читаются как `кто.что()`:

```text
ManualOperationService.create(...)
ManualOperationWriter.update(...)
ImportReviewConfirmationActor.apply(...)
ImportReviewTransferActor.apply(...)
LedgerPostingService.post_imported_income_expense(...)
LedgerPostingService.post_imported_transfer(...)
ImportedOperationCorrection.ignore_confirmed_import(...)
TransferSuggestionUseCase.list_for_document(...)
AccountLedgerReader.get_detail(...)
```

`ManualOperationService` владеет manual API transaction. Import Review API
services владеют своими транзакциями. Chat workflows используют
transaction-neutral Import Review actors напрямую и атомарно фиксируют финансовое
изменение вместе с consume chat state. Внутренний commit не должен появляться в
этих actors.

### Domain

Domain functions и value objects не зависят от HTTP или AsyncSession. Маленькие
чистые вычисления остаются свободными функциями; class/actor нужен для workflow,
state transition или объекта с собственным инвариантом.

`ManualOperationFingerprint.calculate_*` определяет стабильную идентичность
manual write intention для idempotency retry и conflict detection. Эта чистая
domain policy не знает об ORM или transaction boundary.

`RawTransactionStatus` принадлежит imports и объявлен в
`imports/statements/types.py`. Проверки review status и нормализованных полей
принадлежат `import_review/domain/posting.py`. Ledger получает
`LedgerPostingPlan` и повторно проверяет только финансовые инварианты, не
импортируя `RawTransaction` в posting service.

Хорошие свободные функции:

```text
normalize_positive_money(...)
ensure_same_currency(...)
ensure_balanced_transfer(...)
manual_income_expense_amount(...)
clean_description(...)
```

### Mapping

`mapping/manual_read.py` преобразует загруженный operation aggregate в manual
read DTO. `LedgerRecordFactory` в `mapping/records.py` строит неперсистированные
ledger ORM records из уже проверенных application/domain inputs. API mapping
остаётся в API adapter.

Изоморфные Pydantic projections используют прямой
`TargetModel.model_validate(source)`. Именованный mapper сохраняется только там,
где преобразование выражает смысл: выбирает transfer entries, нормализует сумму
или добавляет API capabilities.

Manual и imported factories используют один внутренний confirmed-operation
factory. Он централизованно задаёт `confirmed`, audit fields, `confirmed_at` и
выводит `affects_profit` из `OperationType`. Source-specific factories отвечают
только за команды, provenance metadata и нормализацию входных данных.

### Repository

`LedgerRepository` выполняет только SQLAlchemy queries, add/delete/flush и не
делает commit. Каждый workspace-owned query обязан фильтровать `workspace_id`.
Он не принимает `RawTransaction`: поиск ручных transfer candidates для review
принадлежит `ImportReviewRepository`.
Общий `list_confirmed_operations(...)` обслуживает Reports и Categories, не
принадлежа ни одному из этих consumers. Lookup и row lock подтверждённых
`Operation` для import-review остаются в Ledger. Repository сохраняется единым,
пока `Operation` и `MoneyEntry` используют один persistence contract и одну
транзакционную границу. Read queries можно отделить только при появлении
самостоятельного contract или заметно отличающейся оптимизации; legacy
account-detail queries до React replacement gate не дробятся и не полируются.

## Naming

- `*Service` — публичный application facade для нескольких близких операций.
- `*Writer` / `*UseCase` — write workflow с транзакционными эффектами.
- `*Reviewer` / `*Poster` — вложенная mutation-логика без собственного commit.
- `*Reader` — read-side orchestration и DTO projection.
- `*Repository` — persistence API.
- `*Command` — неизменяемое write-side намерение.
- `*Dto` / `*View` — данные read-side boundary.
- `*Plan` / `*Amounts` — чистый domain result с инвариантами.

## Технический долг

### Legacy account ledger read side

`AccountLedgerReader` и связанные legacy View types остаются временным read-side
adapter для SSR account screen. Их нельзя удалять или заменять новой общей
абстракцией, пока у экрана есть runtime-потребитель.

Долг можно погасить после React cutover account screen, когда:

- React-экран получает account ledger через versioned API;
- legacy account route, presenter и templates больше не используются;
- API и React tests покрывают заменивший их read contract.

До выполнения delete gate в этом коде делаются только исправления корректности
и необходимые изменения контракта.

Если структура или public actors изменяются, этот README обновляется в том же
изменении.
