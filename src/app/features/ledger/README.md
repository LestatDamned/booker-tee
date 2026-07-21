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
- несколько записей одного workflow фиксируются атомарно.

## Основные потоки

```text
manual ledger API / chat
  -> ManualOperationService / ManualOperationWriter
  -> LedgerRepository
  -> Operation + MoneyEntry[]

raw transaction review
  -> RawTransactionPostingUseCase
  -> LedgerPostingPlan + operation mapping
  -> LedgerRepository + ImportRepository
  -> Operation + MoneyEntry[] + linked RawTransaction

account legacy screen
  -> AccountLedgerReader
  -> LedgerRepository
  -> account ledger read model
```

API schemas находятся в `app/api/v1/manual_ledger`. Ledger application layer
не импортирует FastAPI/Pydantic API models и возвращает собственные dataclass
contracts.

## Структура

```text
ledger/
  application/
    account_ledger.py          # legacy account read model and reader
    imported_operations.py     # correction and undo of imported operations
    ledger_reference_resolver.py
    listing.py                 # pagination and query filters
    manual_contracts.py        # manual commands and read DTOs
    manual_mutations.py        # manual write workflows
    manual_operations.py       # public manual service and reference reader
    raw_transaction_posting.py # posting imported rows and transfers
    transfer_suggestions.py    # transfer candidate read workflow

  domain/
    money.py                   # signs, amounts, currency and balance rules
    raw_transactions.py        # posting plan and imported-row policies
    text.py                    # shared ledger text normalization
    types.py                   # operation enums and manual lifecycle policy

  mapping/
    operations.py              # ORM factories, fingerprints and read mapping

  errors.py
  models.py
  repository.py
```

Папки отражают реальные границы, но новый файл не создаётся только ради одного
класса. Несколько небольших actors одной истории могут жить в одном модуле.

## Ответственности

### Application

Application actors оркестрируют workflow, разрешают workspace-scoped references
и владеют commit/rollback своих write-сценариев. Они могут использовать
SQLAlchemy session и repositories, но не знают про HTTP, templates и API schemas.

Public actors читаются как `кто.что()`:

```text
ManualOperationService.create(...)
ManualOperationWriter.update(...)
RawTransactionPostingUseCase.post_raw_transaction(...)
ImportedOperationUndoUseCase.undo_raw_transaction_posting(...)
TransferSuggestionUseCase.list_for_document(...)
AccountLedgerReader.get_detail(...)
```

Если application workflow вызывает другой write workflow, нужно отдельно
проверить владельца transaction boundary: внутренний commit не должен случайно
фиксировать несвязанные изменения вызывающего сценария.

### Domain

Domain functions и value objects не зависят от HTTP или AsyncSession. Маленькие
чистые вычисления остаются свободными функциями; class/actor нужен для workflow,
state transition или объекта с собственным инвариантом.

Хорошие свободные функции:

```text
normalize_positive_money(...)
ensure_same_currency(...)
ensure_balanced_transfer(...)
manual_income_expense_amount(...)
clean_description(...)
```

### Mapping

`mapping/operations.py` — единственная точка создания ledger ORM objects и
преобразования загруженного operation aggregate в manual read DTO. API mapping
остаётся в API adapter.

### Repository

`LedgerRepository` выполняет только SQLAlchemy queries, add/delete/flush и не
делает commit. Каждый workspace-owned query обязан фильтровать `workspace_id`.
Read queries можно вынести в `query_repository.py`, только когда их дальнейший
рост или отдельная оптимизация сделают текущее разделение действительно проще.

## Naming

- `*Service` — публичный application facade для нескольких близких операций.
- `*Writer` / `*UseCase` — write workflow с транзакционными эффектами.
- `*Reader` — read-side orchestration и DTO projection.
- `*Repository` — persistence API.
- `*Command` — неизменяемое write-side намерение.
- `*Dto` / `*View` — данные read-side boundary.
- `*Plan` / `*Amounts` — чистый domain result с инвариантами.

## Текущий cleanup backlog

1. Добавить focused tests для transfer posting, undo и transfer suggestions.
2. Сделать transaction ownership явным для вложенных review/chat workflows.
3. Добавить lifecycle/version policy для correction импортированной операции.
4. Убрать dependency domain raw-transaction policy от imports persistence enum.
5. Удалить `AccountLedgerReader` и связанные legacy View types после React
   cutover account screen.

Если структура или public actors изменяются, этот README обновляется в том же
изменении.
