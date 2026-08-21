# Debts

Статус: действующий финансовый и пользовательский контракт.

`Debt` — workspace-owned расширение одного технического account типа `debt`.
Поддерживаются выданный/полученный заём, кредитная карта и ипотека.

## Модель

- Debt account не доступен в обычном Accounts lifecycle.
- Положительный balance означает, что должны пользователю; отрицательный — что
  должен пользователь.
- Current principal равен initial balance плюс confirmed money entries.
- `DebtPayment` атомарно связывает principal transfer и optional interest
  income/expense.
- Вид долга, currency и principal меняются проводками, а не обычным edit формы.

## Проводки

| Сценарий                 | Principal entry                                               |
| ------------------------ | ------------------------------------------------------------- |
| Пользователь выдаёт заём | обычный account уменьшается, debt account растёт              |
| Получает заём            | обычный account растёт, debt account становится отрицательным |
| Погашает свой долг       | обычный account уменьшается, отрицательный debt идёт к нулю   |
| Получает возврат         | обычный account растёт, положительный debt идёт к нулю        |
| Покупка кредиткой        | расход уменьшает debt account и влияет на profit              |

Principal всегда проводится как balanced transfer с
`affects_profit=false`: он не входит в income, expense, profit, category totals
или property ROI. Interest — отдельная confirmed income/expense operation и
влияет на profit.

Первоначальный долг создаёт стартовую confirmed transfer между debt account и
системным opening-balance account. Это обеспечивает единый ledger и не требует
особого расчёта balance.

## Lifecycle

Состояния: `active`, `settled`, `no_debt` и `archived`. Нулевой principal даёт
`settled` для займа/ипотеки и `no_debt` для кредитной карты, но не удаляет
историю. Платёж можно отменить только атомарно вместе со всеми его операциями.

Debt можно удалить лишь когда после создания не было других платежей, credit-card
expenses или imports; стартовая операция удаляется вместе с ним. Иначе долг
нужно погасить и архивировать.

## Capabilities и безопасность

- Все commands повторно проверяют workspace, role, account ownership и version.
- Idempotency key не создаёт повторный долг или платёж.
- Currency principal accounts должна совпадать.
- Generic manual/import workflow не меняет loan/mortgage principal; credit-card
  expense является явным исключением.
- React отображает server-provided capabilities и не выводит lifecycle из суммы.

## UI

Directory показывает kind, currency, current principal, paid principal и status.
Карточка дополнительно показывает initial amount, interest totals, due date,
credit limit/available limit и последние платежи. Создание и платёж всегда
показывают финансовый результат до подтверждения.

Общие правила `Operation + MoneyEntry` находятся в
[`docs/domain/DOMAIN_MODEL.md`](../../domain/DOMAIN_MODEL.md).
