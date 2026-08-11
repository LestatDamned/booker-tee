# Workspace collaboration hardening

Статус: isolation inventory, explicit small-team limits, PostgreSQL concurrency
gate и two-user browser smoke проверены 11 августа 2026. Реальная SMTP-доставка
invitation остаётся отдельным production rollout gate.

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

Проверено 11 августа 2026:

| Feature family | Read/list evidence | Mutation/boundary evidence |
| --- | --- | --- |
| Accounts и balances | `test_account_detail_returns_workspace_scoped_not_found`, workspace-scoped directory/balance queries | `test_update_rejects_foreign_workspace_before_mutating_account` |
| Operations и money entries | `test_get_masks_an_operation_missing_from_the_workspace` | manual create/update/lifecycle commands carry workspace identity; foreign account/category/property references are rejected before posting |
| Debts и payments | `test_debt_repository_lookups_are_workspace_scoped`, `test_foreign_debt_uses_the_same_not_found_contract` | `test_lifecycle_hides_foreign_debt`, `test_undo_rejects_stale_version_and_foreign_workspace` |
| Documents, parse attempts, raw rows и mapping templates | `test_document_projection_query_is_workspace_scoped_and_deterministic`, foreign document API masking, `test_mapping_template_query_is_workspace_scoped` | review actors load both raw row and locked document through workspace-scoped repositories; cross-workspace classification references are rejected |
| Categories, properties и rules | cross-workspace category detail is hidden; property/rule directories are scoped | `test_property_update_rejects_foreign_or_missing_identity`, `test_create_rejects_foreign_or_missing_target` |
| Reports, dashboard и export | report filters and SQL are workspace-scoped; export uses the same reporting reader | read-only family; no mutation surface exists |
| Members, invitations и activity | foreign workspace directory/activity is masked | foreign member/invitation IDs share the missing-ID outcome and cannot mutate another workspace |
| Chat integrations | active binding lookup is provider/user scoped | `test_workspace_chat_resolver_rechecks_membership_for_existing_binding` proves every callback rechecks active user, workspace and membership |

Repository walk found no global child lookup used by an active workspace workflow.
The parent-child paths for document → parse attempt/raw row, operation → money entry,
debt → payment and activity → linked entity retain workspace scope in their owning
query. The verification reuses feature repositories; no generic tenant repository or
RLS layer was added.

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

Проверено 11 августа 2026 на мигрированной disposable PostgreSQL database:

- invitation create/create на один email сохраняет одну pending invitation и один
  audit event;
- address-bound accept/accept запускается одним eligible actor и создаёт ровно одну
  membership/session transition;
- accept/revoke имеет одного победителя;
- concurrent member role updates дают один commit, один stale conflict и один audit;
- competing ownership transfers сохраняют одного authoritative owner;
- deactivate против invitation create оставляет inactive workspace без pending access
  и переводит session на fallback;
- operation version guard допускает один concurrent commit;
- confirmed raw-row partial unique guard допускает один dedupe hash;
- mapping import idempotency и debt payment/undo сохраняют единственный финансовый
  результат.

Полный targeted PostgreSQL gate дважды подряд: `37 passed`; timeout/deadlock не
зафиксирован. Row locks остались только в authority/multi-row transitions, новых
глобальных lock или retry loops не добавлено.

SQLite/fake repository test не заменяет PostgreSQL lock/constraint test.

### Browser/API

- CSRF на всех mutations;
- no-store/no-referrer на credential-bearing invitation surfaces;
- stale conflict refreshes state without silent retry;
- role change/disable/workspace switch clears stale UI state;
- two users can complete the core smoke flow in one workspace;
- member/invitation limit errors are explicit and usable.

Проверено 11 августа 2026 в headless Chromium на мигрированной disposable
PostgreSQL database и двух изолированных browser contexts:

- address-bound invitation принят подходящим verified user;
- editor загрузил sanitized XLSX fixture и открыл review;
- editor создал операцию, owner увидел ту же committed запись;
- stale edit получил conflict, локальный draft не потерян;
- после смены роли на viewer write control исчез, прямой API write вернул `403`;
- после disable session переключилась на доступный personal workspace;
- private-workspace account второго пользователя остался скрыт с `404`;
- activity показала actor-specific team/finance events и ссылку на операцию;
- viewport `390 × 844` не получил horizontal overflow;
- неожиданных console/page errors не зафиксировано, screenshots не сохранялись.

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
