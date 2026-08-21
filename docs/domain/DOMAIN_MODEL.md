# Booker Tee Domain Model

Статус: канонический справочник финансовых сущностей и инвариантов.

Код моделей подтверждает persistence shape; application/domain services
подтверждают поведение. UI-документы не могут менять финансовый смысл.

## Core model

```text
Workspace
  ├─ Users через WorkspaceMember
  ├─ Accounts
  │    └─ Debts
  ├─ UploadedDocuments
  │    ├─ ParseAttempts
  │    └─ RawTransactions
  ├─ Operations
  │    └─ MoneyEntries
  ├─ Categories
  ├─ Properties
  ├─ TransactionRules
  └─ ImportMappingTemplates
```

### Workspace

Главная ownership boundary. Workspace хранит default currency, type и active
state. Доступ задают membership, role и status; invitations и audit events
также принадлежат workspace.

Любой lookup workspace-owned сущности обязан фильтровать `workspace_id` или
сначала проверить workspace-owned parent.

### Account

Место хранения денег: `cash`, `card`, `deposit`, `checking`, `other`. Значение
`debt` зарезервировано для технического счёта сущности `Debt`.

- имеет currency и initial balance;
- может быть archived;
- баланс выводится из initial balance и confirmed `MoneyEntry`;
- masked account/card data не заменяет workspace authorization.

Debt account не создаётся, не редактируется и не архивируется через общий
Accounts workflow.

### Debt и DebtPayment

`Debt` — workspace-owned расширение одного account типа `debt`. Вид долга:
выданный заём, полученный заём, кредитная карта или ипотека. Текущий principal
равен `Account.initial_balance + confirmed MoneyEntry`:

- положительный баланс — должны пользователю;
- отрицательный баланс — должен пользователь;
- нулевой баланс — principal погашен.

`DebtPayment` атомарно связывает до двух операций одного платежа: principal
transfer и interest income/expense. Principal всегда проводится как
`transfer`, имеет `affects_profit=false` и не попадает в profit, category totals
или property ROI. Interest проводится отдельно и влияет на profit.

Generic manual/import workflow не меняет principal. Исключение: расход по
кредитной карте может использовать её debt account. Loan и mortgage accounts в
общие формы не попадают. Полный контракт находится в
[`docs/features/debts/README.md`](../features/debts/README.md).

### Operation

Экономический смысл денежного события.

```text
type: income | expense | transfer | adjustment
status: draft | needs_review | confirmed | ignored | duplicate
source: manual | bank_pdf | debt | system
```

Operation имеет optimistic `version`, optional category/property, даты,
idempotency metadata и один или несколько `MoneyEntry`.

Ручные, подтверждённые импортированные, долговые и системные записи представлены
в одном пользовательском потоке. `source` определяет provenance и допустимый
correction workflow, но не создаёт отдельную финансовую сущность. UI/API contract
зафиксирован в [`docs/features/operations/README.md`](../features/operations/README.md).

### MoneyEntry

Подписанное движение по одному account:

- отрицательное — деньги ушли;
- положительное — деньги пришли;
- currency хранится явно;
- amount — `Numeric(14, 2)` в БД и `Decimal` в Python.

Official balances используют только entries активных confirmed operations.

### Category

Причина income/expense или аналитическая классификация. Поддерживает hierarchy,
kind, system categories, ordering и archive/active state.

### Property

Необязательная аналитическая привязка операции к объекту. Property не меняет
двойственную природу transfer и не превращает transfer в ROI.

### TransactionRule

Workspace-scoped правило для suggestion/auto-application:

- `contains` или `exact`;
- inflow/outflow/any;
- optional account и amount range;
- target operation type/category/property/description/`affects_profit`;
- priority и active state.

Rule может предложить или подготовить данные, но application boundary повторно
проверяет финансовые инварианты.

## Financial rules

### Income

Обычно одна положительная entry на source account:

```text
Operation(type=income, affects_profit=true)
Account +amount
```

### Expense

Обычно одна отрицательная entry:

```text
Operation(type=expense, affects_profit=true)
Account -amount
```

### Transfer

Две entries одной currency с нулевой суммой:

```text
Source      -amount
Destination +amount
Operation(type=transfer, affects_profit=false)
```

Transfer:

- не является income или expense;
- не влияет на profit, category totals или property ROI;
- требует разных source/destination accounts;
- не может стать profit-affecting из-за UI classification.

### Adjustment

Используется только для явной корректировки с понятным audit trail. Adjustment
не является универсальным обходом income/expense/transfer validation.

## Import model

### UploadedDocument

Сохранённый источник импорта. Хранит workspace, account, filename, storage key,
SHA-256, file metadata и lifecycle:

```text
uploaded
pending_parse
parsing
parsed
requires_review
failed_to_parse
imported
ignored
```

Файл и document record создаются до parse. `storage_key` — internal detail и не
публикуется browser API.

### ParseAttempt

Каждый запуск parser/extractor — отдельная запись:

```text
running | success | requires_review | failed
```

Сохраняет sanitized error, raw text/tables, control totals и validation report.
Ошибка не удаляет document или предыдущие attempts.

### RawTransaction

Строка между extraction и ledger:

- immutable raw payload/fields;
- normalized date/description/amount/currency/balance;
- account, suggestions, confidence и dedupe hash;
- optional linked confirmed operation;
- review lifecycle status.

Актуальные значения enum находятся в
`src/app/features/imports/domain/types.py`; frontend получает typed API values и
не изобретает свои persistence statuses.

`ready_to_confirm` — read/presentation state из server capability и blocking
reasons, не database status.

### ImportMappingTemplate

Workspace-scoped сохранённое соответствие колонок для неизвестной выписки.
Mapping preview не мутирует ledger. Mapping import создаёт reviewable
`RawTransaction`, после чего пользователь проходит обычный review.

## Import pipeline

```text
upload and preserve
  -> ParseAttempt
  -> extract raw text/tables
  -> known parser OR unknown analysis/mapping
  -> normalize
  -> validate and deduplicate
  -> user review
  -> confirmed Operation + MoneyEntry
```

Правила:

1. Parser никогда не создаёт confirmed operation.
2. Raw source сохраняется даже при ошибке.
3. Один upload создаёт один parse attempt; общего пользовательского reparse
   нет.
4. Ignore/delete запрещены при linked operations.
5. Dedupe работает до posting; confirmed dedupe hash дополнительно защищён
   уникальным workspace-scoped индексом.
6. Mapping/import retry не должен повторно создавать строки.

## Status and correction

- Draft/review/ignored/duplicate rows не влияют на official balance.
- Confirmed operation влияет через `MoneyEntry`.
- Ignored operation исключается из активного финансового результата, сохраняя
  историю.
- Confirmed records не hard-delete через обычный UI.
- Edit/cancel/restore используют optimistic version и application policies.
- Raw row и linked operation должны оставаться трассируемыми.

## Reporting

Reports используют confirmed operations и entries:

- income/expense входят в profit по `affects_profit`;
- transfer исключается;
- category/property totals не включают internal transfer;
- account balance считается по account entries, поэтому обе стороны transfer
  видны на соответствующих accounts;
- currency нельзя молча смешивать или конвертировать без явной policy.
- debt interest входит в profit, debt principal transfer исключается.

## Non-negotiable invariants

1. Workspace isolation.
2. `Decimal`/`Numeric`, никогда `float`.
3. Explicit currency.
4. Transfer имеет нулевую сумму entries и `affects_profit=false`.
5. Raw imported data и parse history сохраняются.
6. Review перед ledger posting.
7. Duplicate/idempotency не допускает double-count.
8. Financial commands атомарны.
9. Browser, templates и integrations не владеют financial policy.
10. Приватные payloads не логируются и не отправляются наружу.
11. Debt principal изменяется только debts workflow; generic исключение
    разрешено только для расхода кредитной карты.
