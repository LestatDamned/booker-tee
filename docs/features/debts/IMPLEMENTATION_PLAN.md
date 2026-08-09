# Debts: пошаговая реализация

Статус: Steps 1–8 implemented 2026-08-09; ручной authenticated browser smoke
остаётся эксплуатационной проверкой.

Шаги выполняются по порядку. Каждый шаг оставляет работающий проверяемый срез и
не добавляет код будущих шагов заранее.

## Целевая граница

```text
React debts
  -> /api/v1/debts
  -> DebtService / DebtReader
  -> debt policies + repositories + LedgerPostingService
  -> Debt + DebtPayment + Account + Operation + MoneyEntry
```

Начальная feature остаётся простой:

```text
src/app/features/debts/
  domain.py
  models.py
  schemas.py
  repository.py
  creation.py
  payments.py
  idempotency.py
  service.py
```

Отдельные `application/`, `mapping/` или несколько service-файлов появляются
только когда один файл действительно начинает рассказывать разные истории.
Простое перекладывание одноимённых полей не требует mapper-класса.

Публичный domain API читается как `кто.что()`:

```text
DebtPolicy.resolve_status(...)
DebtPolicy.resolve_capabilities(...)
DebtPaymentPlanner.build(...)
DebtPortfolio.summarize(...)
```

Техническая нормализация денег остаётся приватными функциями: отдельный класс
без состояния и самостоятельного поведения ей не нужен.

## Шаг 1. Domain rules

Статус шага: completed 2026-08-08.

### Результат

Чистый Python-код умеет рассчитывать знаки, статусы, capabilities, доступный
лимит, currency totals и план principal/interest проводок.

### Реализовать

- `DebtKind` и `DebtStatus`;
- нормализацию положительных пользовательских сумм;
- проверку допустимого знака balance для каждого kind;
- status resolver с явно переданным balance и lifecycle;
- `available_credit = credit_limit - outstanding`;
- группировку totals по currency;
- payment plan для receivable и payable направлений;
- запрет погашения principal сверх outstanding;
- validation `opened_on`, `maturity_date`, `original_principal` и credit limit.

Не использовать `date.today()` внутри domain policy. Если дата потребуется,
application передаёт её явно.

### Тесты

- receivable использует положительный balance;
- payable, credit card и mortgage используют отрицательный balance;
- нулевой loan становится `settled`, нулевая credit card — `no_debt`;
- archived имеет приоритет над balance status;
- principal transfer не влияет на profit;
- payable interest — expense, receivable interest — income;
- разные валюты не смешиваются;
- переплата principal отклоняется;
- available credit считается корректно.

### Exit gate

Domain tests проходят без AsyncSession, ORM и FastAPI imports.

Реализовано в `src/app/features/debts/domain.py`; 24 focused cases закреплены в
`tests/features/debts/test_domain.py`. Ruff, ty и focused pytest прошли.

## Шаг 2. Persistence и migration

Статус шага: completed 2026-08-08.

### Результат

База данных хранит `Debt` и связанный составной `DebtPayment`.

### Реализовать

- заменить четыре debt-specific `AccountType` одним `AccountType.DEBT`;
- убрать debt-specific `credit_limit` и `due_date` из общего `Account`;
- добавить `Debt` и `DebtPayment` по контракту из `DOMAIN_MODEL.md`;
- добавить relationships только там, где есть runtime consumer;
- создать deterministic Alembic migration для enum, таблиц, FK, indexes и
  constraints;
- добавить workspace-scoped repository methods;
- расширить `OperationSource` значением `debt` и миграцией enum.

Migration должна учитывать, что текущий debts-код ещё не имеет production
данных. Не писать speculative data migration без существующих строк.

### Тесты

- model values сохраняют `Decimal`, не float;
- workspace-scoped lookup не видит чужой Debt и DebtPayment;
- creation/payment idempotency keys уникальны внутри workspace;
- FK не допускают потерянные связанные записи;
- migration проходит upgrade с предыдущего head.

### Exit gate

Alembic upgrade проходит на PostgreSQL, repository tests доказывают workspace
isolation.

Реализованы `AccountType.DEBT`, модели `Debt` и `DebtPayment`,
workspace-scoped `DebtRepository` и миграция `20260808_0023`. Общий accounts
workflow не показывает и не создаёт технические debt accounts. Upgrade,
downgrade и повторный upgrade проверены на PostgreSQL; focused persistence,
accounts и API tests прошли.

## Шаг 3. Read side

Статус шага: completed 2026-08-08.

### Результат

Application reader возвращает корректный список долгов, totals и detail без
HTTP-зависимостей.

### Реализовать

- один bounded workspace query списка с account balance aggregate;
- включить `initial_balance` в текущий balance;
- агрегировать только confirmed operations;
- построить DTO списка, totals и detail;
- получить историю долга ограниченной страницей;
- рассчитать capabilities на server;
- показывать principal и interest history через связанные ledger operations.

Reader принимает `can_write`; mapper/function не хардкодит permissions или
наличие settlement account.

### Тесты

- opening balance попадает в outstanding;
- ignored/draft/duplicate entries не попадают;
- totals объединяют долги одной валюты и разделяют разные валюты;
- viewer получает read-only capabilities;
- archived debt остаётся читаемым;
- foreign workspace ничего не возвращает;
- количество queries не растёт на каждый долг.

### Exit gate

Read DTO полностью выражает список и карточку без обращения React к ORM или
самостоятельных финансовых расчётов.

Реализованы `DebtReader.list(...)` и `DebtReader.get_detail(...)`, immutable
application DTO и bounded workspace-scoped queries. Список выполняется одним
query; detail использует один query состояния, count и ограниченную страницу
истории. Баланс и общие суммы principal/interest учитывают только confirmed
operations, capabilities рассчитывает `DebtPolicy`, а история сохраняет ссылки
на обе ledger operations. SQL проверен на PostgreSQL с confirmed и ignored
fixture.

## Шаг 4. Создание долгов

Статус шага: completed 2026-08-09.

### Результат

Пользователь может добавить существующий долг либо создать новый долг вместе с
реальным денежным transfer.

### Сценарии

1. `add_existing_debt`:
   создаёт Debt + debt Account с подписанным initial balance, без фиктивного
   движения по обычному счёту.
2. `give_loan`:
   создаёт receivable Debt с нулевым initial balance и transfer с funding
   account.
3. `take_loan`:
   создаёт payable или mortgage Debt и transfer на receiving account.
4. `open_credit_card`:
   создаёт credit card Debt с limit и optional opening debt.

### Правила

- все суммы во входной команде положительные;
- linked account и Debt имеют одну currency;
- funding/receiving account активен и принадлежит workspace;
- transfer accounts различаются;
- команды имеют обязательный idempotency key;
- создание Debt, Account и opening transfer фиксируется одной транзакцией;
- application переиспользует ledger money policies и posting primitives.

### Тесты

- четыре сценария создают правильный знак остатка;
- give/take создают balanced transfer и `affects_profit=false`;
- opening existing debt не создаёт fake Operation;
- currency mismatch и foreign account отклоняются;
- одинаковый retry не удваивает долг или деньги;
- другой payload с тем же ключом даёт conflict;
- ошибка после создания Account откатывает весь сценарий.

### Exit gate

Каждый create workflow атомарен и доказан тестом financial entries.

Реализованы `DebtService.add_existing_debt(...)`, `give_loan(...)`,
`take_loan(...)` и `open_credit_card(...)`. `DebtCreator` валидирует команды,
workspace/currency account boundary и idempotent replay; `DebtService` владеет
commit/rollback. Opening transfer переиспользует
`LedgerPostingService.post_debt_transfer(...)`, создаёт balanced entries с
`source=debt` и `affects_profit=false`. Одинаковый retry не создаёт повторных
записей, другой payload конфликтует. Атомарность и rollback после создания
Account проверены отдельными PostgreSQL-тестами.

## Шаг 5. Платёж и отмена

Статус шага: completed 2026-08-09.

### Результат

Пользователь записывает principal и interest одной формой и может безопасно
отменить ошибочный платёж целиком.

### Реализовать

- `record_payment` с debt account, settlement account, principal, interest,
  date, interest category, notes и idempotency key;
- направление principal transfer по DebtKind;
- interest expense для payable/mortgage/credit card;
- interest income для receivable;
- один `DebtPayment`, связывающий до двух operations;
- атомарный `undo_payment`, переводящий обе operations в неучитываемое состояние
  с audit trail;
- optimistic/replay protection для undo.

Сумма principal или interest может быть нулевой, но не обе одновременно.

### Тесты

- principal уменьшает абсолютный outstanding;
- principal не меняет profit;
- interest правильно меняет profit;
- principal + interest создаются атомарно;
- только interest и только principal поддерживаются;
- excessive principal отклоняется;
- archived/settled debt блокирует payment;
- retry не создаёт вторую пару operations;
- undo отменяет обе части и восстанавливает balance/profit;
- foreign workspace не может прочитать или отменить payment.

### Exit gate

После create, retry и undo ledger, debt balance и reports остаются согласованы.

Реализованы `DebtService.record_payment(...)` и `undo_payment(...)`.
`DebtPaymentRecorder.record(...)` блокирует Debt на время расчёта остатка,
проверяет workspace, активность и валюту settlement account, строит проводки
через `DebtPaymentPlanner` и сохраняет principal/interest с одним
`DebtPayment`. Principal использует balanced transfer и не влияет на profit;
interest создаётся как income для receivable или expense для остальных видов.

`DebtPaymentReverser.reverse(...)` атомарно переводит обе связанные operations
в `ignored` и записывает `reversed_at`. Клиент передаёт видимые в detail версии
operations: устаревшая первая отмена получает conflict, а точный повтор уже
выполненной отмены безопасно возвращает тот же результат. Debt row lock не даёт
двум параллельным платежам одновременно погасить один и тот же остаток.

Unit-тесты покрывают направления, частичные формы платежа, переплату,
архивирование, idempotency, версии и workspace isolation. PostgreSQL-тесты
подтверждают итоговые ledger entries, profit semantics, rollback второй части
платежа и полное восстановление confirmed balance после undo.

## Шаг 6. Versioned JSON API

Статус шага: completed 2026-08-09.

### Результат

React получает стабильный typed contract.

### Маршруты

```text
GET  /api/v1/debts
GET  /api/v1/debts/{debt_id}
POST /api/v1/debts
POST /api/v1/debts/{debt_id}/payments
POST /api/v1/debts/{debt_id}/archive
POST /api/v1/debts/{debt_id}/restore
POST /api/v1/debt-payments/{payment_id}/undo
```

Если одна create request с discriminator остаётся понятной, не создавать четыре
почти одинаковых endpoint. Разделить endpoint только при реально разных HTTP
contracts.

### Контракт

- money передаётся decimal strings;
- UUID и даты используют стандартные API representations;
- idempotency key передаётся согласованным способом с manual ledger;
- API возвращает capabilities и stable reason codes;
- API не возвращает ORM, подписанные внутренние суммы, CSS tones или labels;
- auth и CSRF следуют существующим API dependencies;
- not-found не раскрывает существование чужого объекта.

### Тесты

- unauthenticated/forbidden/read-only matrix;
- request validation и stable error envelope;
- workspace isolation;
- decimal-string response;
- idempotency conflict;
- create/payment/undo happy paths;
- OpenAPI schema включает новые contracts.

### Exit gate

API tests проходят, TypeScript schema regenerated, drift check чистый.

Реализован versioned API в `src/app/api/v1/debts/`. Один create endpoint
принимает discriminated request с `action`: `add_existing`, `give_loan`,
`take_loan` или `open_credit_card`. Create и payment требуют заголовок
`Idempotency-Key`; суммы принимаются и возвращаются decimal strings.

GET-маршруты используют `DebtReader`, mutation-маршруты — `DebtService` и не
обращаются к ORM/repository напрямую. Ответы возвращают server-side
capabilities, reason codes, bounded payment history и версии связанных
operations для безопасного undo. Ошибки имеют единый API envelope; чужой и
несуществующий долг дают одинаковый `debt_not_found`.

Для заявленных archive/restore добавлен application actor
`DebtLifecycleManager.archive()/restore()`: архивировать можно только долг с
нулевым principal, а expected active state и `updated_at` защищают от stale
request. OpenAPI и generated TypeScript contract обновлены.

## Шаг 7. React UI

### Результат

Пользователь проходит полный debts workflow без обращения к общей форме
Accounts.

### Реализовать по порядку

1. Route и список долгов с totals по currency.
2. Форма добавления существующего долга.
3. Формы `выдал заём` и `получил заём`.
4. Карточка с условиями и bounded history.
5. Форма платежа с явным разделением principal/interest.
6. Archive/restore и undo payment.

Переиспользовать существующие AppShell, panels, fields, buttons, MoneyValue,
error states, focus patterns и CSS tokens. Не вводить новый form framework или
глобальный store.

### UX правила

- пользователь вводит только положительные суммы;
- перед сохранением видит preview: что уменьшает principal и что станет
  income/expense;
- currency всегда видима;
- нельзя смешать RUB debt и USD settlement account;
- credit card с нулём показывает `Долга нет`, но остаётся активной;
- maturity date подписана `Конечный срок`, не `Следующий платёж`;
- UI не показывает `Просрочено`;
- loading, empty, filtered-empty, forbidden, validation, conflict и network
  error имеют отдельные состояния;
- действия доступны с клавиатуры и восстанавливают focus после panel/dialog.

### Тесты

- runtime response schemas;
- список и multi-currency totals;
- create flows;
- payment preview и submission;
- validation/capabilities/conflict/network errors;
- archive/restore/undo;
- desktop, tablet и mobile reflow без horizontal page overflow.

### Exit gate

Полный browser flow работает на desktop/tablet/mobile, console и network errors
отсутствуют.

Реализованы канонические React routes `/app/debts` и
`/app/debts/:debtId`. Список показывает активные/архивные долги и отдельные
totals для каждой валюты. Одна create panel поддерживает четыре утверждённых
сценария, но раскрывает только поля выбранного сценария.

Карточка показывает условия, principal, interest и bounded history. Payment
panel заранее объясняет, какая часть уменьшит основной долг и какая станет
доходом или расходом. Archive/restore и undo используют server capabilities,
expected snapshots и общие confirmation/focus patterns. Для undo в API history
добавлен `canUndo`, поэтому React не выводит финансовое разрешение из ролей или
статусов самостоятельно.

UI собран из существующих AppShell, Workbench, panel, field, money, status,
feedback и responsive collection компонентов. Новые зависимости, form
framework и global store не добавлялись. Runtime contract, четыре create
commands, multi-currency totals, payment preview/submission, lifecycle и undo
покрыты frontend tests.

## Шаг 8. Интеграция и завершение

Статус шага: implemented 2026-08-09.

### Проверить consumers

- Accounts directory не показывает debt Account как обычный создаваемый счёт;
- manual ledger может записать расход кредитки, но не предлагает loan/mortgage
  accounts и не редактирует `source=debt` operations;
- Import Review может проводить расход по credit card debt account;
- generic manual/import API не позволяет обойти debts workflow и создать
  principal transfer напрямую;
- account detail корректно показывает source target для debt operations;
- Reports включают interest и исключают principal transfer;
- Categories и Properties не считают principal расходом или ROI;
- chat integrations не получают новые write actions без отдельного решения;
- API/generated frontend contracts согласованы.

### Документация

- дополнить общий `docs/domain/DOMAIN_MODEL.md` сущностями Debt/DebtPayment;
- добавить debts flow в architecture только если появляется новая устойчивая
  граница;
- обновить roadmap status;
- отметить выполненные шаги здесь и удалить устаревшие утверждения прототипа.

### Полные проверки

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest

cd frontend
npm run check
```

Также выполнить migration upgrade на PostgreSQL и authenticated browser smoke
flow.

### Финальный gate

- transfer никогда не влияет на profit;
- principal и interest разделены;
- opening balance и confirmed entries согласованы;
- currencies не смешиваются;
- workspace isolation доказан tests;
- retries не удваивают долг или payment;
- undo не оставляет половину платежа;
- React является единственным browser frontend debts;
- все новые файлы имеют runtime consumer.

Интеграция закрыта общей server-side проверкой account usage. Обычные account
списки, transfer options и chat integrations не получают debt accounts.
Manual ledger и statement upload получают только активные credit card debt
accounts; расход разрешён, а income и generic transfer отклоняются даже при
прямом вызове API. Loan и mortgage accounts остаются только в debts workflow.

Account detail распознаёт `source=debt` и ведёт обратно в карточку долга.
Reports, Categories и Properties продолжают использовать `affects_profit`:
principal transfer исключается, interest income/expense учитывается. Общая
domain model и roadmap обновлены; новая общая architecture boundary не
добавлялась, потому что существующий `React -> API -> application -> repository`
flow не изменился.

Полный backend gate: Ruff, ty и `917 passed, 26 skipped`. Отдельные PostgreSQL
debt tests: `4 passed`; Alembic прошёл от пустой базы до `20260808_0023`.
Frontend gate: format, lint, styles, API contract, typecheck и `530 passed`;
production build прошёл. Интерактивный authenticated browser smoke не запускался:
в рабочем окружении нет browser runner, поэтому он остаётся ручной проверкой.

## Шаг 9. Обслуживание записи долга

Статус шага: implemented 2026-08-09.

### Редактирование

`DebtDetailsEditor.update()` принимает полный набор безопасных полей и
`expected_updated_at`. Разрешены название, notes, даты и лимит кредитки.
`original_principal` и текущий баланс не выдаются за редактируемые поля. Текущий
баланс проверяется повторно на сервере, поэтому новый
лимит кредитки нельзя установить ниже фактической задолженности. Kind, currency
и balance не входят в API request.

### Удаление

`DebtDeleter.delete()` удаляет связку `Debt + Account`, если после создания долг
не использовался. Для займа допускается ровно одна стартовая `source=debt`
transfer-операция: она удаляется в той же транзакции. Uploaded documents, raw
transactions, `DebtPayment`, расходы кредитки и любые дополнительные операции
блокируют удаление. Проверка workspace и optimistic snapshot обязательны.

### Проверки

- unit tests safe fields, validation, stale snapshot и все группы blockers;
- API tests PUT/DELETE contracts и workspace write permission;
- React runtime schema, edit panel, confirmation и server capabilities;
- regenerated OpenAPI/TypeScript contract и полный backend/frontend gate.

## После первой версии

Не добавлять заранее. Следующий самостоятельный slice возможен после реального
использования:

```text
DebtObligation / payment schedule
  -> next payment
  -> due soon
  -> overdue
  -> reminders
```

Затем отдельно могут появиться процентные ставки, расчёт графика, условия
кредитки и контрагенты. Они не должны менять уже проведённые ledger facts.
