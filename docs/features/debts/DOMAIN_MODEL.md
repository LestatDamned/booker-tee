# Debts: финансовая модель

Статус: целевой контракт первой версии.

## Сущности

### Account

Каждый `Debt` имеет один внутренний `Account` типа `debt`. Его баланс всегда
выводится по общему правилу проекта:

```text
Account.initial_balance + confirmed MoneyEntry
```

Draft, ignored и duplicate операции остаток не меняют.

Debt accounts:

- не создаются и не меняют вид через общую форму Accounts;
- используют ту же валюту, что и `Debt`;
- архивируются только через debts workflow.

Изменять principal можно только через debts workflow. Исключение — расход по
кредитной карте: credit card debt account может быть account расходной manual
или imported операции. Погашение кредитки остаётся principal transfer в
`debts`. Loan и mortgage accounts не предлагаются как обычные accounts в
manual/import forms.

### Debt

`Debt` является workspace-owned расширением account один-к-одному.

Минимальные поля:

```text
account_id          UUID, primary key и FK -> accounts.id
workspace_id        UUID, FK -> workspaces.id, indexed
kind                DebtKind
opened_on           date | null
original_principal  Numeric(14, 2) | null
maturity_date       date | null
credit_limit        Numeric(14, 2) | null
creation_idempotency_key  UUID
creation_fingerprint      String(64)
created_at          datetime
updated_at          datetime
```

Название, currency, notes и lifecycle уже принадлежат связанному `Account` и
не дублируются.

`maturity_date` — конечный срок договора. Это не дата следующего платежа и не
основание для статуса `overdue`.

### DebtKind

```text
loan_receivable — пользователь выдал заём
loan_payable    — пользователь получил заём
credit_card     — задолженность по кредитной карте
mortgage        — ипотечный principal
```

В общем `AccountType` достаточно одного нового значения `debt`. Вид долга
принадлежит `Debt.kind` и не расширяет общую форму счетов четырьмя специальными
вариантами.

### DebtPayment

Один пользовательский платёж может состоять из двух разных экономических
событий: principal transfer и interest income/expense. Они должны быть связаны
в одну атомарную и отменяемую запись.

Минимальная связь:

```text
id                       UUID
workspace_id             UUID
debt_account_id          UUID
principal_operation_id   UUID | null
interest_operation_id    UUID | null
idempotency_key          UUID
idempotency_fingerprint  String(64)
notes                    text | null
created_at               datetime
reversed_at              datetime | null
```

Хотя бы одна из сумм principal или interest должна быть больше нуля. Уникальный
`(workspace_id, idempotency_key)` защищает весь платёж, а не отдельную его
часть.

Для отмены UI передаёт версии обеих связанных `Operation`. Первая отмена
допустима только для ожидаемых confirmed-версий; повтор уже выполненной отмены
возвращает тот же `DebtPayment`. Обе операции становятся `ignored` в одной
транзакции, а `reversed_at` сохраняет факт отмены.

## Денежные инварианты

Все пользовательские суммы положительные и преобразуются в подписанные entries
в domain/application слое.

### Остаток

```text
loan_receivable                       balance >= 0
loan_payable, credit_card, mortgage   balance <= 0
```

В первой версии principal-платёж не может перевести долг через ноль. Например,
при остатке `30 000 RUB` нельзя записать погашение principal `35 000 RUB`.

Положительная переплата по кредитке пока не поддерживается.

### Первоначальная сумма

`original_principal` — справочный факт договора, а не источник текущего
остатка. Текущий остаток всегда берётся из account balance.

- для займа и ипотеки первоначальная сумма больше нуля;
- для кредитки она может отсутствовать;
- `credit_limit` задаётся только для кредитки и должен быть больше нуля;
- opening debt кредитки не может превышать лимит;
- если обе даты заданы, `maturity_date >= opened_on`.

## Проводки

### Пользователь выдал заём

```text
Обычный account   -100 000
Debt account      +100 000
Operation: transfer, affects_profit=false, source=debt
```

### Пользователь получил заём

```text
Debt account      -200 000
Обычный account   +200 000
Operation: transfer, affects_profit=false, source=debt
```

### Пользователь погашает свой долг

Платёж `50 000`, из них `12 000` principal и `38 000` interest:

```text
Principal operation:
  Обычный account   -12 000
  Debt account      +12 000
  transfer, affects_profit=false

Interest operation:
  Обычный account   -38 000
  expense, affects_profit=true
```

Обе операции имеют `source=debt` и связаны одним `DebtPayment`.

### Пользователю возвращают выданный долг

Получено `22 000`, из них `20 000` principal и `2 000` interest:

```text
Principal operation:
  Debt account      -20 000
  Обычный account   +20 000
  transfer, affects_profit=false

Interest operation:
  Обычный account    +2 000
  income, affects_profit=true
```

### Покупка кредитной картой

```text
Debt account       -5 000
Operation: expense, affects_profit=true
Category: Продукты
```

Такая операция может прийти из manual ledger или import review. Погашение
кредитки записывается debts workflow как principal transfer.

### Существующий долг при первом добавлении

Если денежное событие произошло до начала работы в Booker Tee, остаток задаётся
через подписанный `Account.initial_balance`:

```text
Выданный долг       +70 000
Полученный долг     -70 000
Кредитка            -25 000
Ипотека         -4 200 000
```

Фиктивное движение по обычному account не создаётся.

## Статусы

Статус выводится из вида, account lifecycle и текущего остатка:

```text
archived — account неактивен
settled  — заём или ипотека имеют нулевой остаток
no_debt  — активная кредитка имеет нулевой остаток
active   — активный долг имеет ненулевой остаток
```

Кредитка с нулевым балансом остаётся открытой. Нулевой остаток не архивирует
долг автоматически.

`overdue` не входит в первую версию. Конечный срок ипотеки 2044 года ничего не
говорит о том, внесён ли обязательный платёж за текущий месяц.

## Capabilities

Server вычисляет доступность действий.

- Запись платежа требует financial write permission, активный debt, ненулевой
  principal или interest и подходящий активный settlement account той же
  валюты.
- Principal нельзя погасить сверх текущего остатка.
- Архивирование разрешено только при нулевом principal.
- Безопасное редактирование меняет только название, notes, `opened_on`,
  `maturity_date` и `credit_limit`. `kind`, currency, `original_principal` и
  opening/current balance через эту команду не меняются.
- Удаление разрешено без импортов, `DebtPayment` и последующих операций.
  Единственная `source=debt` transfer-операция, созданная вместе с займом,
  удаляется атомарно вместе с долгом и возвращает второй account к исходному
  балансу. Opening balance сам по себе не считается историей.
- Любая финансовая история навсегда переводит запись на безопасный путь
  `погасить -> архивировать`; hard delete в этом случае запрещён.
- Generic Account edit/archive не изменяет debt account.
- Generic manual/import workflow не создаёт principal transfer для debt
  account.
- Generic manual/import correction не изменяет операции `source=debt`.
- Отмена платежа принадлежит debts workflow и отменяет обе связанные операции
  атомарно.

API возвращает booleans и стабильный `readonly_reason_code`; React не повторяет
эти правила.

Команды update, delete, archive и restore передают ожидаемый `updated_at`.
Stale request получает conflict и не перезаписывает более свежие изменения.

## Итоги

Итоги группируются по currency:

```text
receivable   = сумма положительных debt balances
payable      = абсолютная сумма отрицательных debt balances
net_position = receivable - payable
```

Пример:

```text
Займ Ивану       +70 000 RUB
Кредитка        -120 000 RUB
Ипотека       -4 200 000 RUB

receivable       70 000 RUB
payable       4 320 000 RUB
net_position -4 250 000 RUB
```

USD и RUB возвращаются отдельными строками.

## Транзакции и идемпотентность

- Public debts service владеет commit/rollback.
- Вложенные writers/repositories только flush-ят изменения.
- Создание долга вместе с transfer атомарно.
- Principal и interest одного платежа атомарны.
- Уникальный `(workspace_id, creation_idempotency_key)` защищает создание
  Debt, включая сценарии без opening Operation.
- Повтор того же idempotency key с тем же payload возвращает прежний результат.
- Повтор ключа с другим payload возвращает conflict.
- Все lookups фильтруют `workspace_id`, включая загрузку DebtPayment и связанных
  operations.

## Будущее расширение

График добавляется отдельной сущностью обязательства и не меняет текущий ledger:

```text
DebtObligation
  debt_account_id
  due_date
  amount_due
  amount_paid
  status
```

Только после этого можно достоверно добавить `due_soon`, `overdue`, минимальный
платёж и reminders.
