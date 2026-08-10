# Workspace collaboration hardening

Статус: целевой verification contract; значительная часть механизмов
уже реализована.

## Цель

Этот slice не добавляет новую collaboration capability. Он доказывает,
что существующие и новые workflows безопасны при:

- двух и более active users;
- simultaneous writes;
- stale browser tabs;
- foreign workspace/member/entity IDs;
- retry после network failure;
- member disable, leave, ownership transfer и workspace deactivate;
- небольшой, но явно ограниченной team size.

## Неизменные инварианты

1. Любой workspace-owned read/write фильтрует `workspace_id` или сначала
   проверяет strictly workspace-owned parent.
2. URL/body/cookie workspace ID не является authority.
3. Inactive membership не даёт read capability.
4. `Workspace.owner_id` и единственный active owner membership совпадают.
5. Ownership, invitation consume/revoke, member transition и lifecycle mutation
   сериализуются workspace row lock.
6. Stale mutation не перезаписывает committed state.
7. Retry-sensitive create использует idempotency key и command fingerprint.
8. Boundary-changing mutation переводит sessions/chat bindings в безопасное
   committed state в той же transaction.
9. Public invitation surfaces не раскрывают membership, email и token state.
10. Raw financial data не попадают в audit/log/error payloads.

## Workspace-scoped repository gate

Для каждой workspace-owned entity должен быть один authoritative lookup pattern:

```python
select(Operation).where(
    Operation.id == operation_id,
    Operation.workspace_id == workspace_id,
)
```

Допустим parent-first pattern:

```python
document = await documents.get(
    workspace_id=workspace_id,
    document_id=document_id,
)
if document is None:
    raise DocumentNotFoundError()

rows = await raw_transactions.list_for_document(document.id)
```

Недопустим global lookup child ID с последующей browser-side check.

Verification inventory:

- accounts и balances;
- operations/money entries/manual ledger;
- debts и debt payments;
- documents/parse attempts/raw transactions/mapping templates;
- categories/properties/transaction rules;
- reports/dashboard/export;
- members/invitations/audit events;
- chat integrations, bindings и callbacks.

Проверка не дублирует every query в отдельном generic repository. Она
закрепляет текущие feature repositories и их application callers.

## Optimistic concurrency contract

Команда передаёт committed token именно той entity, которую меняет:

| Entity/workflow              | Expected token                              |
| ---------------------------- | ------------------------------------------- |
| confirmed/manual operation   | integer `version`                           |
| workspace settings/lifecycle | `workspace.updated_at`                      |
| member role/status/leave     | `member.updated_at`                         |
| ownership transfer           | workspace and recipient `updated_at`        |
| invitation revoke            | `invitation.updated_at`                     |
| current workspace switch     | expected current workspace ID               |
| mutable reference entity     | existing entity version/updated-at contract |

Application flow:

```text
lock authoritative row/parent
  -> re-resolve actor membership
  -> compare expected token
  -> validate transition and financial invariants
  -> mutate all related rows
  -> append audit event when applicable
  -> commit once
```

Conflict возвращает `409` с stable code. React:

1. не повторяет stale write автоматически;
2. загружает fresh state;
3. сообщает, что данные изменились в другой вкладке/другим
   участником;
4. не merge финансовые draft автоматически.

## Pessimistic concurrency contract

Workspace row lock применяется только для multi-row authority transitions,
где optimistic token не может защитить общий инвариант:

- ownership transfer;
- invitation create/accept/revoke;
- member disable/reactivate/leave;
- workspace deactivate/restore;
- expected-current workspace switch/session move where required.

Обычные financial reads и independent entity updates не блокируют весь
workspace. Если в будущем workspace lock станет measured bottleneck, lock scope
сужается по конкретному invariant.

## Explicit small-team limits

Текущие directories ограничены 100 rows. Целевой product contract не
молча обрезает список, а явно ограничивает workspace:

```text
MAX_WORKSPACE_MEMBERS = 100
MAX_PENDING_INVITATIONS = 100
```

- member limit считает active и disabled memberships; removed historical rows не
  занимают active seat;
- existing removed membership recovery занимает seat и проверяет limit;
- pending limit считает только unexpired pending rows;
- create invitation под workspace lock отклоняет превышение с
  `member_limit_reached` или `pending_invitation_limit_reached`;
- member/invitation directory возвращает весь допустимый набор;
- activity и большие financial lists используют pagination, а не
  модель seat limit.

Пагинация members добавляется вместо лимита только после явного
product decision поддерживать большие команды.

## Session and boundary transitions

### Disable/remove member

В одной transaction:

- membership теряет active status;
- all active sessions с этим current workspace переводятся на active
  fallback или теряют current workspace;
- workspace chat access отзывается;
- audit event записывается;
- stale requests выключённого user не проходят context resolution.

### Deactivate workspace

- owner authority и optimistic token повторно проверяются под lock;
- pending invitations revoked;
- active sessions move to per-user fallback;
- chat/integration consequences applied;
- no financial rows hard-deleted;
- restore не восстанавливает revoked invitations или removed members
  автоматически.

### Boundary navigation

Workspace switch, accept, leave, ownership consequences и lifecycle transitions возвращают
navigation outcome. React делает hard navigation, чтобы сбросить:

- cached API responses;
- local financial drafts;
- stale session capabilities;
- entity IDs предыдущего workspace.

## Database constraints

Сохраняются:

- unique `(workspace_id, user_id)` membership;
- unique invitation token hash;
- foreign keys и workspace indexes;
- idempotency uniqueness на workflows, где она уже часть contract.

Единственный active owner и agreement с `Workspace.owner_id` продолжают
гарантироваться locked application transition и PostgreSQL concurrency tests.
Не добавляется trigger или partial unique index, который может сломать
атомарную смену двух membership rows. К DB-level invariant возвращаются
только с доказанным migration/transfer design.

## Why no PostgreSQL RLS now

Текущий deployment имеет один FastAPI backend и один database access model.
Application context и repositories уже владеют workspace scope. RLS потребует
безошибочного transaction-local workspace context в async connection pool и усложнит
migrations, maintenance и tests.

RLS пересматривается, если появится хотя бы одно:

- direct user/analyst SQL access;
- external BI connections;
- multiple backend services с разными database principals;
- измеренный recurring repository-scoping defect;
- отдельное compliance requirement.

## Required test matrix

### Isolation

Каждый active feature имеет минимум:

- foreign entity ID returns not-found/forbidden according to privacy contract;
- same entity-shaped ID in another workspace never reads/mutates data;
- list/report/export contains only current workspace rows;
- relationship child cannot escape through foreign parent;
- chat callback re-resolves workspace membership.

### Concurrency

PostgreSQL tests покрывают:

- concurrent expected-current workspace switches;
- concurrent idempotent workspace create;
- invitation create for same email;
- invitation accept versus accept;
- invitation accept versus revoke;
- member role/status stale update;
- ownership transfer versus competing transfer/disable;
- workspace deactivate versus member/invitation mutation;
- confirmed operation stale edit/cancel/restore;
- import review posting/deduplication races.

SQLite/fake repository test не заменяет PostgreSQL lock/constraint test.

### Browser/API

- CSRF на всех mutations;
- no-store/no-referrer на credential-bearing invitation surfaces;
- stale conflict refreshes state without silent retry;
- role change/disable/workspace switch clears stale UI state;
- two users can complete the core smoke flow in one workspace;
- member/invitation limit errors are explicit and usable.

## Two-user smoke flow

1. Owner creates workspace and address-bound editor invitation.
2. Second verified user accepts it.
3. Both sessions select the same workspace.
4. Editor creates a manual draft/operation; owner sees the committed financial event.
5. Owner and editor open the same mutable record; one commits, the stale write gets
   conflict and refreshes.
6. Editor uploads/reviews a sanitized fixture according to role policy.
7. Owner changes editor to viewer; the second session loses write controls after hard
   refresh and direct write API is forbidden.
8. Owner disables the member; active sessions and chat bindings lose workspace access.
9. Owner sees committed administrative and financial events on the activity page.
10. Neither user can address an entity from the other user's private workspace.

## Exit gate

Hardening complete when:

- repository isolation inventory has tests, not only a checklist;
- targeted PostgreSQL concurrency suite passes against a migrated database;
- two-user browser smoke passes with sanitized data;
- no list silently truncates below the supported product limit;
- OpenAPI/frontend contracts contain current capabilities and conflict codes;
- full Ruff, ty, pytest and frontend checks pass;
- runtime workspace README and user guide match implemented behavior.
