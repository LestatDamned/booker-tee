# Workspace activity journal

Статус: administrative activity backend и embedded settings section реализованы.
Целевое решение Stage 4 — отдельная manager-only страница с объединёнными
административными и значимыми финансовыми событиями.

Решение принято 10 августа 2026: не размазывать постоянные строки авторства по
карточкам и dense lists. Основной UX аудита — отдельный журнал действий.

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

Ссылка «История действий» находится в workspace settings. Текущая embedded
секция Stage 3 удаляется после достижения parity отдельной страницей.

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
- entity event содержит безопасную ссылку на доступную операцию или документ;
- empty/loading/error/retry/load-more states не блокируют navigation;
- timestamps используют общий frontend formatter;
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

- operation created/updated/cancelled/restored;
- document uploaded;
- import confirmed.

Новые financial event types добавляются только для различимого business action,
а не ради UI label. Category/account/rule mutations, bulk diff и arbitrary entity
history остаются вне первой версии до подтверждённого сценария.

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

Существующие `Operation.created_by_user_id`, `Operation.updated_by_user_id` и
`UploadedDocument.uploaded_by_user_id` продолжают заполняться как entity metadata,
но не являются источником полноценной истории: они не сохраняют промежуточные
действия. В первой версии отдельные actor-блоки в каждой карточке не требуются.

## Safe event details

`details` остаётся узким allowlisted snapshot, а не arbitrary payload store.

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
читаемости истории после lifecycle change.

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
- repository всегда явно фильтрует `workspace_id`;
- foreign workspace возвращает privacy-safe `404`;
- active non-manager получает `403 workspace_activity_forbidden`.

Typed projection:

```text
WorkspaceActivityItemDto
  id
  event_type
  scope: team | finance
  actor: { id, display_name } | null
  target: { id, display_name } | null
  entity: { type, id, display_label, href } | null
  summary_code
  details: typed safe fields
  created_at
```

Backend возвращает stable `summary_code` и typed details; React форматирует
русскую строку. ORM model и произвольный JSON наружу не выдаются.

## Permissions

Первая версия остаётся manager-only:

- owner/admin видят `all`, `team` и `finance`;
- остальные active roles не получают журнал;
- capability остаётся `can_view_workspace_activity`;
- наличие ссылки на entity не заменяет entity authorization.

Расширять журнал на editor/viewer можно только отдельным product decision, потому
что события могут раскрывать имена документов, суммы и действия других людей.

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
- actor берётся из authenticated workspace context;
- owner/admin читают журнал, другие роли не читают;
- foreign workspace и foreign entity не раскрываются;
- details не содержат credentials или raw financial payload;
- `all/team/finance` filters стабильны между keyset pages;
- одинаковые timestamps не создают gaps или duplicates;
- historical Stage 3 events остаются читаемыми;
- React покрывает filters, entity links, empty/error/retry/load-more;
- отдельная страница достигает parity, после чего embedded settings section
  удаляется.

Stage 4 завершён, когда owner/admin может на отдельной странице объяснить
последовательность значимых team и financial mutations только по persisted server
events, без восстановления истории из текущего состояния entities.
