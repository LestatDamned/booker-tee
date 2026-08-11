# Workspace activity journal

Статус: Stage 4 реализован. Отдельная manager-only React-страница объединяет
административные и значимые финансовые события; прежняя embedded settings section
удалена после достижения parity.

Решение принято 10 августа 2026: не размазывать постоянные строки авторства по
карточкам и dense lists. Основной UX аудита — отдельный журнал действий.

## Принятые архитектурные решения

1. Это operational activity log, не Event Sourcing и не compliance audit.
2. Расширяется существующий `WorkspaceAuditEvent`; вторая audit table не создаётся.
3. Originating application service владеет единственной DB transaction.
4. Узкий `WorkspaceActivityWriter` пишет typed/versioned events и не делает commit.
5. Idempotent replay определяется до append и никогда не создаёт новое событие.
6. Event names соответствуют реальным commands, включая delete и undo.
7. API не выдаёт arbitrary JSON и не знает React `href`.
8. Scope выводится из explicit event-type mapping, а не хранится независимо.
9. Outbox появляется только вместе с external consumer/dual write.
10. Новые indexes добавляются только по результатам PostgreSQL query plan.

## Цель

Owner/admin должен получать ответы на вопросы:

1. кто изменил команду или authority workspace;
2. кто создал, изменил, отменил или восстановил финансовую запись;
3. кто загрузил документ и подтвердил импорт;
4. когда произошло committed действие и к какой entity оно относится.

Это журнал значимых mutations, а не тотальная аналитика поведения. Reads, клики,
report views и внутренние `MoneyEntry` inserts не записываются.

## Целевой React UX

Канонический route:

```text
/app/workspaces/:workspaceId/activity
```

Ссылка «История действий» находится в workspace settings. Журнал не дублируется
в карточках или секциях настроек.

Первая версия страницы:

```text
История действий

[Все] [Финансы] [Команда]

Сегодня
14:20  Анна изменила операцию «Лукойл»
13:45  Максим подтвердил импорт statement.pdf
12:10  Максим пригласил anna@example.com

Вчера
18:30  Анна отменила операцию «Кофемания»
17:15  Максим изменил роль Анны
```

- filters отражаются в URL и работают с keyset pagination;
- entity event получает ссылку только для доступной сущности с известным
  canonical React route; удалённая или неподдерживаемая entity остаётся текстом;
- empty/loading/error/retry/load-more states не блокируют navigation;
- timestamps форматируются в `ru-RU` с датой и временем;
- после committed local mutation достаточно reload first page;
- realtime subscription не нужна.

## Scope первой версии

### Команда и workspace

- workspace created/updated/deactivated/restored;
- invitation created/revoked/accepted;
- member role changed;
- member disabled/reactivated/left;
- ownership transferred.

### Финансы

- manual operation created/updated/cancelled/restored/deleted;
- debt created/updated/archived/restored/deleted;
- debt payment recorded/undone;
- document uploaded;
- import review item/transfer confirmed;
- import review posting undone.

Новые financial event types добавляются только для различимого business action,
а не ради UI label. До enum migration write-path inventory обязан проверить
manual, imported, transfer, undo, upload и idempotent replay commands. Generic
`IMPORT_CONFIRMED` не используется, если реальный use case подтверждает один
review item или transfer. Category/account/rule mutations, bulk diff и arbitrary
entity history остаются вне первой версии до подтверждённого сценария.

## Persistence decision

Расширяется существующий append-only `WorkspaceAuditEvent`. Вторая generic audit
table не создаётся: текущая модель уже имеет workspace, actor, target/entity,
typed event и timestamp.

```text
WorkspaceAuditEvent
  workspace_id
  actor_user_id
  target_user_id | null
  event_type
  entity_type
  entity_id | null
  details
  created_at
```

`WorkspaceAuditEvent` — operational activity log, но не source of truth. Ledger,
balances и entity state никогда не восстанавливаются replay событий; authoritative
state остаётся в `Operation`, `MoneyEntry`, `UploadedDocument` и связанных domain
models. Это не Event Sourcing и не CQRS projection store.

Существующие `Operation.created_by_user_id`, `Operation.updated_by_user_id` и
`UploadedDocument.uploaded_by_user_id` продолжают заполняться как entity metadata,
но не являются источником полноценной истории: они не сохраняют промежуточные
действия. В первой версии отдельные actor-блоки в каждой карточке не требуются.

## Safe event details

`details` остаётся узким allowlisted snapshot, а не arbitrary payload store.
Каждый writable event type получает отдельную Pydantic details model с
`payload_version`; feature code не передаёт generic `dict[str, Any]`.

```python
class OperationUpdatedActivityDetails(BaseModel):
    payload_version: Literal[1] = 1
    display_label: str
    changed_fields: tuple[OperationChangedField, ...]
```

Допустимо:

| Event            | Safe details                                    |
| ---------------- | ----------------------------------------------- |
| workspace update | changed fields и old/new non-secret values      |
| invitation       | role; invitee email только в manager projection |
| member change    | old/new role или status                         |
| operation action | operation kind и короткий safe display label    |
| document upload  | sanitized display filename                      |
| import confirm   | result counts без raw row payload               |

Никогда не сохраняются:

- invitation/session tokens и auth data;
- raw statement text, tables или extracted payload;
- account/card numbers;
- полный snapshot операции или документа;
- request headers, cookies и user-agent.

Если UI может получить безопасный label из доступной entity, event хранит только
`entity_type` и `entity_id`. Snapshot добавляется только когда он нужен для
читаемости истории после lifecycle change. Для deleted entity safe display label
обязателен, потому что entity уже нельзя разрешить. Details не используются для
arbitrary filtering, поэтому GIN/JSON indexes в первой версии не добавляются.

## Module boundaries

Financial/import application services не импортируют 800-line
`WorkspaceRepository`. Activity persistence выделяется в узкую cohesive boundary:

```text
workspaces/
  application/
    activity.py          # manager-only reader
    activity_writer.py   # typed event-specific writes, no commit
  activity_repository.py # append/list queries only
```

`WorkspaceActivityWriter` предоставляет named methods вроде
`operation_updated(...)` и `document_uploaded(...)`; generic public
`emit(event_type, payload)` не допускается. Writer валидирует payload и вызывает
`WorkspaceActivityRepository`, но не владеет commit/rollback.

Protocol, event bus и generic Unit of Work не добавляются при одной SQLAlchemy
implementation. Originating application service остаётся transaction owner.

## Transaction semantics

Application use case записывает event в той же transaction, что и mutation:

```text
authorize and lock
  -> validate expected state / idempotency
  -> mutate financial or workspace entity
  -> append WorkspaceAuditEvent
  -> commit
```

Нельзя:

- commit business change и затем отдельно записывать event;
- писать event до stale-version или idempotency checks;
- создавать duplicate event при replay;
- создавать event для rejected/rolled-back mutation;
- принимать actor ID из request body вместо authenticated context.

System action может иметь `actor_user_id = null` только при действительно
безличном workflow и показывается как «Система».

### Idempotency outcome

Use case обязан различать новую mutation и replay до append события. Manual create
получает внутренний typed result:

```python
@dataclass(frozen=True)
class ManualOperationCreateOutcome:
    operation: Operation
    replayed: bool
```

`replayed=True` возвращает существующий persisted result и не создаёт activity
event. Import/upload workflows переиспользуют существующий `replayed` contract.
Отдельный activity `dedupe_key` не добавляется, пока recorder не исполняется
независимо от основной команды; existing entity constraints, optimistic version и
explicit outcome остаются единственным механизмом.

### Проверенный manual-operation write path

Проверено по application code 10 августа 2026:

| Command                             | Transaction owner            | Успешный event               | No-event outcome                             |
| ----------------------------------- | ---------------------------- | ---------------------------- | -------------------------------------------- |
| API create income/expense/transfer  | `ManualOperationService`     | `manual_operation_created`   | matching replay, race replay, conflict       |
| Chat create income/expense/transfer | `ChatManualOperationService` | `manual_operation_created`   | rejected command или rollback state consume  |
| update                              | `ManualOperationService`     | `manual_operation_updated`   | stale version, validation/lifecycle conflict |
| cancel                              | `ManualOperationService`     | `manual_operation_cancelled` | stale version или lifecycle conflict         |
| restore                             | `ManualOperationService`     | `manual_operation_restored`  | stale version или lifecycle conflict         |
| delete                              | `ManualOperationService`     | `manual_operation_deleted`   | stale version или lifecycle conflict         |

`ManualOperationWriter` делает flush/savepoint, но не commit. API service и chat
service являются двумя реальными originating services, поэтому append нельзя
спрятать только в API router. `ManualOperationCreateOutcome` теперь различает новую
операцию и immediate/race replay; публичный API contract не меняется.

Для delete writer возвращает внутренний `ManualOperationDeleteOutcome` с
`operation_id`, типом и safe `display_label`, снятыми до удаления. Это часть
интеграции activity, а не новая публичная DTO.

### Реализованный manual-operation activity slice

Реализовано 10 августа 2026:

- append/list запросы вынесены в узкий `WorkspaceActivityRepository`;
- `WorkspaceActivityWriter` записывает versioned allowlisted payload без commit;
- API create/update/cancel/restore/delete и chat create пишут событие внутри
  originating transaction;
- authenticated actor берётся только из `WorkspaceContext`;
- immediate/race replay не пишет повторное событие, а ошибка append приводит к
  rollback финансовой mutation;
- unified reader классифицирует event через explicit `team | finance` mapping;
  отдельная страница читает `all | finance | team` через URL-owned scope.

### Проверенный import-review write path

Проверено по application code 10 августа 2026:

| Command                                       | Transaction owner                                                | Успешный event                     | No-event outcome                                            |
| --------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------- | ----------------------------------------------------------- |
| confirm income/expense row                    | `ImportReviewConfirmationService`                                | `import_review_item_confirmed`     | immediate/race replay, stale row, validation conflict       |
| create transfer или match raw rows            | `ImportReviewTransferService`                                    | `import_review_transfer_created`   | immediate/race replay, stale candidate, validation conflict |
| link row к existing manual operation/transfer | `ExistingOperationLinkService` или `ImportReviewTransferService` | `import_review_operation_linked`   | target-state replay или stale candidate                     |
| undo imported posting                         | `ImportReviewUndoService`                                        | `import_review_posting_undone`     | replay или stale operation                                  |
| unlink row от manual operation                | `ImportReviewUndoService`                                        | `import_review_operation_unlinked` | repeated unlink конфликтует и не пишет event                |
| update imported operation review fields       | `ImportedOperationReviewUseCase`                                 | `imported_operation_updated`       | stale version, invalid reference или non-editable operation |

Confirmation, transfer и undo actors делают только mutation/flush; перечисленные
outer services владеют commit/rollback. Создание rule внутри confirmation остаётся
частью одного user command и не создаёт второй activity event.

`ImportReviewConfirmationResult`, `ImportReviewUndoResult` и
`ImportReviewExistingOperationLinkResult` уже различали replay. В
`ImportReviewTransferResult` добавлены `operation_id` и `replayed`, потому что
раньше new mutation и replay были неразличимы, а target operation терялась до
transaction owner.

`ExistingOperationLinkService` принимает `WorkspaceContext`; actor нельзя
передавать отдельным request полем. Raw-row lifecycle `ignore/restore` не меняет
ledger и остаётся вне finance activity первой версии.

### Реализованный import-review activity slice

Реализовано 10 августа 2026:

- confirmation, transfer creation/raw-row match и linking пишут отдельные
  command-specific events;
- undo импортированного posting и unlink от manual operation различаются по
  `OperationSource` и пишут разные события;
- редактирование review fields пишет `imported_operation_updated`;
- `ExistingOperationLinkService` теперь принимает authenticated
  `WorkspaceContext`, а не отдельный `workspace_id`;
- safe payload содержит только document/item UUID и affected counts; raw row,
  суммы, реквизиты и extracted payload не сохраняются;
- replay/conflict/rollback не создают события, append выполняется до единственного
  commit originating service.

### Проверенный debt/system-operation write path

Проверено по application code 10 августа 2026:

| Command                                                      | Transaction owner | Успешный event                    | No-event outcome                                           |
| ------------------------------------------------------------ | ----------------- | --------------------------------- | ---------------------------------------------------------- |
| add existing debt / give loan / take loan / open credit card | `DebtService`     | `debt_created`                    | immediate/race replay, validation или idempotency conflict |
| record payment                                               | `DebtService`     | `debt_payment_recorded`           | immediate/race replay, invalid balance/account/category    |
| undo payment                                                 | `DebtService`     | `debt_payment_undone`             | replay, stale version или inconsistent operation state     |
| update details                                               | `DebtService`     | `debt_updated`                    | stale snapshot или invalid terms                           |
| archive / restore                                            | `DebtService`     | `debt_archived` / `debt_restored` | stale snapshot или lifecycle conflict                      |
| delete unused debt                                           | `DebtService`     | `debt_deleted`                    | stale snapshot или financial-history conflict              |

`DebtCreator`, `DebtPaymentRecorder` и `DebtPaymentReverser` теперь возвращают
typed outcomes с `replayed`. `DebtDeleter` уже возвращает safe name до удаления.
Это позволяет append выполнить до единственного `DebtService` commit и не писать
event на replay.

Одна debt-команда создаёт ровно одно domain-level activity event. Внутренние
`OperationSource.DEBT` principal/interest/opening-transfer operations и их
`MoneyEntry` не получают собственных activity events: один платёж может атомарно
создать две операции, но для пользователя остаётся одним действием. Отдельного
user-facing `system operation` command в текущем коде нет; создание system
categories при posting также не является activity.

### Реализованный debt activity slice

Реализовано 10 августа 2026:

- единый `DebtService` записывает `debt_created`, payment recorded/undone,
  updated, archived/restored и deleted перед своим commit;
- create/payment outcomes используют `replayed`, поэтому immediate/race replay не
  создаёт второе событие;
- event entity — debt account; payment event дополнительно хранит только safe
  `payment_id`, delete — короткий name snapshot;
- внутренние principal/interest/transfer операции не получают отдельных событий;
- отдельного system-operation event нет, потому что соответствующей пользовательской
  команды в текущем продукте не существует.

### Проверенный document-upload write path

`StatementUploadUseCase` имеет три последовательные transaction boundaries:

1. сохранить файл, создать `UploadedDocument`, append `document_uploaded`, commit;
2. создать running `ParseAttempt`, commit;
3. сохранить parse result/failure и raw source, commit.

Activity event относится только к первой transaction. Immediate и race replay уже
возвращают `StatementUploadResult(replayed=True)` и не должны append новое событие.
Ошибка document/activity write откатывает transaction и удаляет сохранённый файл;
эта cleanup-ветка покрывает не только `IntegrityError`. Ошибка последующего parsing
не отменяет `document_uploaded`, потому что document и raw input уже сохранены.

Отдельного reparse/retry command в текущем API нет. Mapping import имеет собственный
`replayed` contract, но меняет способ разбора уже загруженного документа и остаётся
вне finance activity первой версии. Document ignore/delete также пока вне scope;
если их включить позже, `ImportDocumentManagementUseCase` должен принимать
authenticated `WorkspaceContext`, а delete event обязан сохранить safe filename до
удаления.

### Реализованный document-upload activity slice

Реализовано 10 августа 2026:

- `document_uploaded` записывается после создания `UploadedDocument` и до первого
  commit;
- actor берётся из `WorkspaceContext`, entity указывает на uploaded document;
- details содержит только `payload_version` и sanitized display filename, без
  storage key, hash, raw text или extracted payload;
- immediate/race replay не создаёт событие;
- ошибка document/activity write откатывает DB transaction и удаляет сохранённый
  файл; parse failure после первого commit сохраняет upload event.

### File-storage boundary

`DOCUMENT_UPLOADED` пишется до первого document commit, в одной DB transaction с
`UploadedDocument`. Любая ошибка document/event write вызывает rollback и cleanup
сохранённого файла; `IntegrityError` replay остаётся отдельной веткой. Ошибка
последующего parsing не отменяет upload event: document и raw source уже сохранены.

## Read model и API

Существующий endpoint расширяется, новый параллельный API не создаётся:

```http
GET /api/v1/workspaces/{workspaceId}/activity
    ?scope=all|finance|team
    &limit=50
    &beforeCreatedAt=2026-08-10T08:00:00Z
    &beforeId=<uuid>
```

- default scope `all`, limit `50`, maximum `100`;
- cursor fields передаются только вместе;
- ordering `(created_at DESC, id DESC)`;
- filter входит в cursor/query contract и не меняется между pages;
- response cursor содержит `scope`, и React использует его при загрузке следующей
  page;
- repository всегда явно фильтрует `workspace_id`;
- foreign workspace возвращает privacy-safe `404`;
- active non-manager получает `403 workspace_activity_forbidden`.

Typed projection:

```text
WorkspaceActivityItemDto
  id
  scope: team | finance
  actor: { id, display_name } | null
  target: { id, display_name } | null
  entity: { type, id, display_label, is_available } | null
  summary_code
  details: typed safe fields
  created_at
```

Backend возвращает stable `summary_code` и typed details; React форматирует
русскую строку. ORM model и произвольный JSON наружу не выдаются. Application/API
DTO не содержит React `href`: frontend строит canonical route по известному
`entity.type`, а target endpoint повторно проверяет workspace authorization.
Для `operation` целевой deep link определён в
[`../operations/README.md`](../operations/README.md):
`/app/operations?operation_id=<uuid>`.

Stage 3 `eventType` сохраняется в v1 response только для backward compatibility,
но React использует один presentation discriminator — `summaryCode`. Новые
event types регистрируются в одном explicit projector mapping; exhaustiveness test
доказывает, что каждый visible event имеет scope и safe projection.
Entity availability разрешается bounded batch queries по типам entities на одну
page; per-event lookups и N+1 queries не допускаются.
Первая версия выдаёт entity references для `workspace`, `operation`, `debt` и
`uploaded_document`. Invitation/member остаются в typed `target/details`: отдельных
canonical routes для них нет, поэтому искусственная ссылка не создаётся.

## Permissions

Первая версия остаётся manager-only:

- owner/admin видят `all`, `team` и `finance`;
- остальные active roles не получают журнал;
- capability остаётся `can_view_workspace_activity`;
- наличие ссылки на entity не заменяет entity authorization.

Расширять журнал на editor/viewer можно только отдельным product decision, потому
что события могут раскрывать имена документов, суммы и действия других людей.

## Operational history, not compliance audit

Первая версия отвечает «кто выполнил значимое действие», но не доказывает
неизменность истории перед администратором БД и не восстанавливает точный old state.
Она не заявляется как forensic/compliance audit, потому что:

- workspace hard delete может cascade-delete rows;
- safe summary не является полным financial diff;
- нет tamper-evident signature/read-only archive;
- retention policy сознательно не определена.

Если появится legal/compliance requirement, проектируется отдельный retention,
tamper evidence, privileged access monitoring и immutable archive. Это не
расширение UI-фильтра.

## Outbox decision

Outbox/queue не нужны, пока entity mutation и activity event записываются в одну
PostgreSQL transaction и журнал читается из той же БД. Outbox добавляется только
при реальном dual write: external broker, independent async projection,
notification consumer или compliance archive. Тогда consumers обязаны быть
idempotent и принимать at-least-once delivery.

## Index decision

Текущий `(workspace_id, created_at, id)` обслуживает `all` без лишнего event-type
filter и keyset ordering. `team/finance` реализованы через explicit event type set. Composite
`(workspace_id, event_type, created_at, id)` добавляется только после PostgreSQL
`EXPLAIN (ANALYZE, BUFFERS)` на representative volume; speculative indexes не
входят в Stage 4.

Baseline 10 августа 2026 после migration `0029`: локальная БД содержит `3022`
events в `1905` workspaces, максимум `10` events на workspace. На этом маленьком
worst-case `all` использует backward index-only scan (`0.126 ms`), `team` —
workspace bitmap scan + in-memory sort (`0.118 ms`), `finance` без matching rows —
event-type index (`0.070 ms`). Эти числа подтверждают корректный query shape, но
не являются representative performance evidence для нового composite index.

## Out of scope

- audit reads, page opens, reports и searches;
- каждое внутреннее ledger posting или `MoneyEntry`;
- realtime/WebSocket;
- CSV/export и arbitrary search;
- сохранение полного old/new financial payload;
- бессрочная compliance retention policy;
- отдельный экран истории каждой entity.

## Tests и exit gate

- каждое поддержанное committed действие создаёт ровно один event;
- rejected/conflicting/idempotently replayed действие не создаёт event;
- manual create и import/upload явно возвращают replay outcome;
- actor берётся из authenticated workspace context;
- owner/admin читают журнал, другие роли не читают;
- foreign workspace и foreign entity не раскрываются;
- details не содержат credentials или raw financial payload;
- every visible event имеет typed versioned payload, scope и projector;
- upload event failure откатывает document row и очищает stored file;
- `all/team/finance` filters стабильны между keyset pages;
- одинаковые timestamps не создают gaps или duplicates;
- historical Stage 3 events остаются читаемыми;
- React покрывает filters, entity links, empty/error/retry/load-more;
- отдельная страница достигает parity, после чего embedded settings section
  удаляется.

Stage 4 завершён, когда owner/admin может на отдельной странице объяснить
последовательность значимых team и financial mutations только по persisted server
events, без восстановления истории из текущего состояния entities.
