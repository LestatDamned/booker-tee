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
│   ├── operations.py
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

Статус: in progress.

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

### 3. Account ledger projections

Статус: pending.

- перевести account ledger read models на Pydantic;
- заменить механические Account/Category/Property mappings на
  `Model.model_validate(...)`;
- сохранить вычисление balance, direction и account-scoped operation view;
- не расширять legacy SSR boundary.

### 4. Mapping cohesion

Статус: pending.

- отделить idempotency fingerprint, ORM record construction и manual read
  projection;
- использовать ясные actor APIs;
- не создавать package facades или generic mapper framework.

### 5. Mutation actors

Статус: pending.

- разделить creation, editing и lifecycle только по реальным transaction и
  behavior boundaries;
- сохранить публичный `ManualOperationService.create/update/cancel/...`;
- не дублировать manual posting между API и chat.

### 6. Repository ownership

Статус: pending.

- убрать dependency `repository -> application`;
- определить ownership report/category/import-review queries;
- не дробить repository механически на короткие forwarding classes.

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
