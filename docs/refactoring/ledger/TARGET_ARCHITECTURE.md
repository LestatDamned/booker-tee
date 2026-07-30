# Ledger Refactoring Target

Статус: активный исполнимый план.

Этот файл является единственным планом рефакторинга `features/ledger`.
Канонические финансовые инварианты остаются в
[`DOMAIN_MODEL.md`](../../domain/DOMAIN_MODEL.md), общие правила слоёв — в
[`ARCHITECTURE.md`](../../architecture/ARCHITECTURE.md).

## Цель

Сделать `ledger` компактной слоистой feature:

- одна видимая transaction boundary на пользовательский workflow;
- Pydantic для commands, DTO, filters и read projections;
- ORM не выходит из публичных application use cases;
- semantic projections остаются явными;
- repository содержит persistence, но не application policy;
- структура сохраняет читаемые actor APIs вида `Class.action`.

Полная hexagonal architecture и Protocol для каждого repository не являются
целью. Новая абстракция добавляется только при существующем повторном
consumer.

## Неподвижные инварианты

1. Workspace scope обязателен для каждого read/write.
2. Income/expense влияет на profit, transfer — нет.
3. Transfer содержит разные accounts одной currency и сбалансированные entries.
4. Financial mutation атомарна.
5. Idempotency retry не создаёт вторую operation.
6. Optimistic version защищает edit/cancel/restore/delete.
7. Import parser не создаёт confirmed ledger records напрямую.
8. Application transaction owner выполняет единственный общий commit/rollback.

## Целевая структура

```text
ledger/
├── models.py
├── repository.py
├── errors.py
├── schemas/
│   ├── manual.py
│   ├── listing.py
│   ├── account_ledger.py
│   └── posting.py
├── application/
│   ├── manual_operations.py
│   ├── manual_creation.py
│   ├── manual_editing.py
│   ├── manual_lifecycle.py
│   ├── account_ledger.py
│   ├── imported_operations.py
│   ├── posting.py
│   └── references.py
├── domain/
│   ├── types.py
│   ├── manual_idempotency.py
│   └── money.py
└── mapping/
    ├── records.py
    └── manual_read.py
```

Это направление, а не требование создать все файлы заранее. Cohesive модуль не
делится только ради симметрии или лимита строк.

## Этапы

### 1. Transaction safety

Статус: completed 2026-07-30.

- lazy system-category seeding получил некоммитящие `ensure_*` operations;
- `LedgerReferenceResolver` использует только caller-owned category transaction;
- commit-owning category screens сохраняют прежние `get_*`/`seed_*` operations;
- idempotency race ручной операции изолирован SQLAlchemy savepoint;
- `ManualOperationWriter` больше не выполняет полный rollback внешней session;
- добавлены tests на отсутствие hidden commit и outer rollback.

Transaction owners после этапа:

```text
Manual Ledger API  -> ManualOperationService
Chat confirmation  -> ChatManualOperationService
Import confirmation/transfer/undo -> соответствующий Import Review actor
Imported review-field edit -> ImportedOperationReviewUseCase
```

Внутренние `ManualOperationWriter`, `LedgerPostingService`,
`LedgerReferenceResolver` и `ImportedOperationCorrection` не завершают общую
транзакцию.

### 2. Pydantic manual contracts

Статус: completed 2026-07-30.

- 2A: перенести manual commands и read DTO в `schemas/manual.py`, перевести их
  на `ApplicationModel` и удалить старый `application/manual_contracts.py`;
- 2B: перенести filters, pagination и reference options;
- 2C: удалить изоморфные constructors, сохранив semantic transfer projection и
  API capabilities;
- наследовать внутренние contracts от immutable `ApplicationModel`;
- удалять только изоморфные constructors;
- сохранить semantic transfer projection и API capabilities.

2A завершён 2026-07-30. Девять manual command/read contracts переведены на
`ApplicationModel`; production, API, chat и tests импортируют их напрямую из
`schemas/manual.py`. Старый defining module удалён без re-export facade.
Dataclass-specific `replace(...)` в API test stub заменён на immutable
`model_copy(update=...)`. Financial behavior, transaction ownership, semantic
mapper и wire format не менялись.

2B завершён 2026-07-30. Pagination, page metadata и query filters перенесены в
`schemas/listing.py`, а reference option DTO — в `schemas/manual.py`; все
contracts переведены на `ApplicationModel`. Старый `application/listing.py`
удалён без re-export facade, поэтому repository больше не зависит от application
ради query data. Нормализация pagination и вычисляемые свойства сохранены без
изменения поведения.

2C завершён 2026-07-30. Изоморфные reference и pagination projections заменены
на явные `TargetModel.model_validate(source)`, а вложенные API references
валидируются Pydantic вместе с response. Удалены приватные constructors и
локальный `NamedReference` Protocol, существовавшие только для копирования
одинаковых полей. Сохранены semantic manual read projection для transfer,
нормализация суммы и description, request mapping и вычисление API capabilities.

### 3. Account ledger projections

Статус: deferred until React account cutover.

Этап сознательно пропущен 2026-07-30: все его runtime consumers принадлежат
legacy SSR account screen и должны быть удалены после React replacement gate.
До cutover здесь выполняются только исправления корректности и необходимые
изменения контракта; отдельная Pydantic-полировка временных projections не
проводится.

### 4. Mapping cohesion

Статус: completed 2026-07-30.

- 4A: вынести semantic manual read projection в `mapping/manual_read.py`;
- 4B: вынести manual idempotency fingerprint из mapping;
- 4C: собрать ORM record construction в `mapping/records.py` и удалить
  `mapping/operations.py`;
- использовать ясные actor APIs;
- не создавать package facades или generic mapper framework.

4A завершён 2026-07-30. `ManualOperationReadMapper.from_operation(...)`
изолирует semantic read projection: выбор transfer source/destination entries,
нормализацию суммы и вложенные references. Production и tests импортируют actor
напрямую из `mapping/manual_read.py`; старое имя
`ManualOperationReadDtoMapper.from_model(...)` удалено без compatibility facade.

4B завершён 2026-07-30. Чистая политика manual idempotency перенесена в
`domain/manual_idempotency.py` и доступна через actor API
`ManualOperationFingerprint.calculate_income_expense(...)` /
`calculate_transfer(...)`. Application writer, ORM factories и tests используют
domain policy напрямую; старые fingerprint functions удалены из mapping без
compatibility facade.

4C завершён 2026-07-30. ORM record construction перенесён в
`mapping/records.py` под actor API `LedgerRecordFactory.build_*`. Source-specific
methods явно различают manual и imported operations, общий confirmed-operation
constructor сохраняет lifecycle, audit и profit invariants. Manual fingerprint
вычисляется writer один раз и передаётся в factory как готовое значение. Старый
`mapping/operations.py` удалён без compatibility facade; package re-exports не
добавлялись.

### 5. Mutation actors

Статус: deferred.

Этап отложен 2026-07-30. Единственная подтверждённая граница — creation,
который совместно используется Manual Ledger API и chat workflow. Разделение
editing и lifecycle потребовало бы дублирования version/load/flush mechanics
или нового технического collaborator. До появления дополнительной причины
сохраняются `ManualOperationService.create/update/cancel/...` и
transaction-neutral `ManualOperationWriter`.

### 6. Repository ownership

Статус: completed 2026-07-30.

Dependency `repository -> application` устранена на этапе 2B: repository
принимает persistence-oriented параметры и не знает application DTO.

`LedgerRepository.list_confirmed_operations(...)` — общий ledger read query,
которым пользуются Reports и Categories. Имя больше не привязывает persistence
contract к одному consumer. Lookup и row lock для `Operation` в import-review
также принадлежат Ledger: review оркестрирует workflow, но не владеет
persistence подтверждённых операций.

`LedgerRepository` намеренно не разделён на command/query/report repositories:
его методы работают с одним aggregate (`Operation` + `MoneyEntry`), используют
одну транзакционную границу и пока образуют читаемый cohesive persistence API.
Короткие forwarding classes и package facades не добавляются. Account-detail
queries остаются до React replacement gate и рассматриваются вместе с legacy
cleanup, а не полируются заранее.

### 7. Legacy cleanup

Статус: pending.

- выполнять после React replacement gate для account detail;
- удалить только adapters и projections без runtime consumer;
- не полировать удаляемый SSR workflow заранее.

## Gate каждого этапа

```bash
uv run ruff check .
uv run ty check .
uv run pytest tests/features/ledger -q
```

Для затронутого consumer дополнительно запускаются его API/chat/import tests.
PostgreSQL concurrency/idempotency tests запускаются отдельно при доступной
`BOOKER_TEE_TEST_DATABASE_URL`.
