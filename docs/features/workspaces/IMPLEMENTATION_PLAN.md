# Workspace collaboration implementation plan

Статус: Stage 1–3 реализованы и прошли automated gates;
authenticated browser/SMTP и multi-role browser smoke остаются rollout-проверками.
Следующий implementation slice — Stage 4.

План доводит уже работающий workspace baseline до адресных
invitations, осмысленных read roles, единой истории значимых действий и явных
isolation/concurrency gates. Каждый stage — вертикальный slice с data, application,
API, React и tests. Не оставлять долгоживущие half-migrated contracts.

## Общие правила

- React не вычисляет permissions из role labels.
- Application use case владеет transaction/commit/rollback.
- Repository всегда видимо фильтрует workspace.
- Credential и private financial payload не попадают в logs/errors/audit.
- Каждая schema change имеет Alembic migration и upgrade/downgrade check.
- API schema и TypeScript типы генерируются, а не редактируются вручную.
- Новый stage не начинается, пока previous exit gate не пройден.
- Completed implementation details сворачиваются в feature README;
  obsolete plan text не живёт вечно.

## Stage 0. Baseline and contract lock

Цель: зафиксировать текущее поведение перед изменением identity и
read permissions.

### Work

1. Run current workspace unit/API/PostgreSQL/React suites.
2. Add missing characterization only where a changed boundary lacks one:
   - bearer invitation accepts any authenticated account today;
   - analyst and viewer currently share read behavior;
   - member/invitation directories currently cap at 100;
   - current activity events and actor fields are inventoried.
3. Inventory active API routes by required capability:
   - general read;
   - raw import read;
   - financial write;
   - import management;
   - member/workspace management.
4. Confirm SMTP-disabled local/test behavior and invitation next-path signup flow.
5. Record sanitized two-user smoke fixture and accounts; do not add real financial data.

### Exit gate

- current baseline tests pass;
- changed route/model inventory is explicit;
- no speculative abstraction is introduced;
- Stage 1 migration assumptions are verified against current data shape.

## Stage 1. Address-bound invitations

Спека: [`EMAIL_BOUND_INVITATIONS.md`](EMAIL_BOUND_INVITATIONS.md).

Статус: реализовано 10 августа 2026. Migration, application/API, email delivery,
React, OpenAPI и automated PostgreSQL/concurrency gates пройдены.

### 1.1 Persistence migration

1. Add nullable `workspace_invitations.invitee_email`.
2. Add `(workspace_id, invitee_email, status)` index.
3. Revoke existing unbound pending invitations in the migration.
4. Update ORM model and migration tests.
5. Run upgrade, downgrade and upgrade on a disposable PostgreSQL database.

Gate: no pending invitation without an email remains after migration; historical rows and
memberships are preserved.

### 1.2 Application create/read/revoke

1. Extend create API command/request with email.
2. Reuse identity `normalize_email`.
3. Add workspace-scoped repository queries for membership email and pending invitation.
4. Under workspace lock:
   - expire old pending rows;
   - reject duplicate pending;
   - reject active/disabled member;
   - enforce member/pending limits;
   - include email and role in idempotency fingerprint.
5. Add invitation email only to manager directory DTO.
6. Keep token/share URL absent from list DTO.
7. Preserve revoke optimistic token and privacy-safe foreign ID handling.

Gate: application and PostgreSQL concurrent-create tests pass.

### 1.3 Accept and membership recovery

1. Require verified authenticated email matching the invitation.
2. Preserve public preview shape without email.
3. Define active/disabled/removed membership outcomes exactly as in the spec.
4. Restore removed membership in place; do not violate unique workspace/user.
5. Consume invitation, switch current session and emit audit event in one transaction.
6. Keep invalid/expired/revoked/replayed token unavailable behavior.
7. Add accept/accept and accept/revoke PostgreSQL race tests.

Gate: wrong-account and losing concurrent requests mutate no row/session.

### 1.4 Delivery and React

1. Add `build_workspace_invitation_message` beside existing identity email builders.
2. Inject existing `IdentityEmailSender` into API route.
3. Schedule send only after successful service commit; keep share URL fallback.
4. Add email field, validation and stable error handling to invitation section.
5. Show pending email/role/expiry to owner/admin.
6. Implement wrong-account accept UX without revealing target email.
7. Regenerate OpenAPI/types and update API adapter/runtime schema tests.
8. Перед production rollout: run authenticated invite -> signup/login -> accept browser
   smoke с реальной SMTP конфигурацией.

### Stage 1 exit gate

- all invitation spec tests pass;
- SMTP configured/disabled paths are both verified;
- tokens/emails are absent from logs and public preview;
- legacy unbound pending invitations cannot be accepted;
- runtime workspace README and user-facing help match new flow.

## Stage 2. Role capability completion

Спека: [`ROLE_CAPABILITIES.md`](ROLE_CAPABILITIES.md).

Статус: реализовано 10 августа 2026. Pure policy, API enforcement,
session/OpenAPI contract, React navigation/role copy и stale-session forbidden
state покрыты automated tests.

### 2.1 Pure policy

1. Extend the explicit role matrix tests to all six roles and inactive statuses.
2. Add only the missing predicates:
   - raw import read;
   - member/invitation directory read;
   - administrative activity read.
3. Add stable API permission errors/dependencies.
4. Keep financial/import/member/workspace predicates unchanged unless route inventory
   proves a mismatch.

Gate: one pure policy table fully describes every role; no generic ACL framework exists.

### 2.2 API enforcement

1. Apply raw-import read dependency to documents, mapping and review reads.
2. Apply member-directory read to member/invitation lists.
3. Recheck application services that have non-HTTP callers.
4. Return privacy-safe not-found for foreign workspace and explicit forbidden for a known
   active actor lacking a capability.
5. Add per-surface analyst/viewer/uploader API tests.

Gate: analyst cannot obtain raw source by direct API request; viewer remains read-only and
uploader cannot use manual/reference mutations.

### 2.3 Session and React

1. Add navigation-level capability flags to session/OpenAPI/TypeScript contracts.
2. Gate navigation and route controls from those flags.
3. Keep entity-specific action decisions in entity DTO capabilities.
4. Explain role differences in invitation/member UI.
5. Hard navigate after authority/boundary changes.
6. Cover stale session where UI shows an old link but API correctly denies access.

### Stage 2 exit gate

- every active API route is assigned to a tested read/write capability;
- React and API behavior agree for all six roles;
- role labels do not drive authorization;
- direct URL/API access cannot bypass hidden navigation.

## Stage 3. Administrative activity

Статус: реализовано. Manager-only reader/API/React используют safe typed
projection, keyset `(created_at, id)` и reload после committed local mutation.

Спека: [`ACTIVITY_AND_AUTHORSHIP.md`](ACTIVITY_AND_AUTHORSHIP.md).

### 3.1 Event semantics

1. Add explicit lifecycle/ownership/leave event types.
2. Keep projection compatibility with historical generic event/action rows.
3. Audit every workspace application mutation for exactly-one committed event.
4. Remove duplicate event creation from legacy/service paths only after proving no runtime
   consumer requires it.
5. Ensure idempotent replay and rejected conflict emit no extra event.

Gate: event semantics are actor/action specific and no secret/financial payload is stored.

### 3.2 Activity reader and API

1. Add workspace-scoped keyset repository query.
2. Add typed safe application projection.
3. Authorize owner/admin through the role policy.
4. Add `GET /api/v1/workspaces/{workspaceId}/activity` with bounded limit and cursor.
5. Add API masking, pagination and schema tests.
6. Regenerate frontend types.

Gate: equal timestamps paginate without duplicate/missing rows; foreign workspace is
masked.

### 3.3 React activity section

1. Add manager-only section to workspace settings.
2. Format stable summary codes and typed details.
3. Add empty/error/loading/load-more states.
4. Refresh/prepend only committed events after local administrative mutations.
5. Check desktop/tablet/mobile and keyboard flow.

### Stage 3 exit gate

- owner/admin can explain recent authority changes from the UI;
- other roles cannot retrieve the activity DTO;
- event history does not require realtime infrastructure.

## Stage 4. Unified workspace activity journal

Спека: [`ACTIVITY_AND_AUTHORSHIP.md`](ACTIVITY_AND_AUTHORSHIP.md).

Решение: финансовые действия не размазываются по карточкам и dense lists.
Stage 4 переносит activity на отдельную страницу и расширяет существующий
`WorkspaceAuditEvent`; actor fields entities продолжают корректно заполняться,
но не заменяют append-only history.

### 4.1 Write-path audit

1. Trace manual create/edit/cancel/restore.
2. Trace import posting and corrections.
3. Trace debt/system operation creation.
4. Trace upload, mapping and retry.
5. Fill existing actor fields and append supported activity events only from
   authenticated `WorkspaceContext`.
6. Keep event append in the same transaction after conflict/idempotency checks.
7. Add the smallest missing application tests per write family.

Gate: every supported committed action has exactly one actor-specific event; rollback,
conflict and replay have none.

### 4.2 Unified activity reader and API

1. Add `team | finance` scope to the typed safe projection.
2. Add safe entity reference and link without exposing arbitrary audit JSON.
3. Extend the existing endpoint with `scope=all|finance|team`.
4. Keep scope stable across keyset pages and mask foreign entities.
5. Regenerate API types and add filtering/pagination tests.

### 4.3 Dedicated React page

1. Add `/app/workspaces/:workspaceId/activity` for owner/admin.
2. Add settings navigation link «История действий».
3. Render `Все / Финансы / Команда`, timeline, entity links and load more.
4. Cover empty/loading/error/retry and keyboard/responsive states.
5. Remove the embedded settings activity section only after feature parity.

### Stage 4 exit gate

- owner/admin can explain significant team and financial mutations from one page;
- displayed history comes from committed persisted events, not current entity state;
- other roles cannot retrieve the journal;
- no realtime, second audit table or per-card authorship UI is required.

## Stage 5. Isolation, concurrency and limit gate

Спека: [`COLLABORATION_HARDENING.md`](COLLABORATION_HARDENING.md).

### 5.1 Explicit limits

1. Introduce `MAX_WORKSPACE_MEMBERS = 100` and `MAX_PENDING_INVITATIONS = 100`
   in the owning workspace application modules.
2. Count seats/statuses according to the spec under workspace lock.
3. Return stable reason codes and actionable React errors.
4. Prove directories return the complete supported set rather than silently truncating.

Gate: the 100/101 boundaries have application and PostgreSQL tests.

### 5.2 Isolation verification

1. Walk the repository inventory in the hardening spec.
2. Reuse existing characterization tests; add a test only for an uncovered boundary.
3. Verify list/report/export and parent-child paths, not only direct `get(id)`.
4. Verify chat callbacks re-resolve membership.
5. Fix any root repository/application boundary defect once, not in each router.

Gate: every active feature family has foreign-workspace read and mutation evidence.

### 5.3 Concurrency verification

1. Run all PostgreSQL workspace concurrency tests on a migrated disposable database.
2. Add missing invitation-email, authority/lifecycle and financial stale-write races.
3. Verify audit events and sessions after winning/losing transactions.
4. Keep row-lock scope limited to authority transitions.
5. Run the complete targeted suite repeatedly enough to detect lock-order deadlocks.

Gate: no race produces two owners, two invitation winners, stale overwrite, duplicate
money or a session pointing at inaccessible workspace.

### 5.4 Two-user browser smoke

Execute the ten-step smoke flow from the hardening spec with sanitized data. Capture only
the result/checklist; do not retain screenshots containing private data.

### Stage 5 exit gate

- targeted and full backend/frontend quality checks pass;
- disposable PostgreSQL migration and concurrency checks pass;
- two-user authenticated browser smoke passes;
- user/runtime docs are current;
- remaining realtime/comments/custom-role/RLS ideas stay explicitly out of scope.

## Commands

Backend baseline:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

PostgreSQL tests use a disposable migrated database through
`BOOKER_TEE_TEST_DATABASE_URL`; never point them at a development or production database
with user data.

Frontend:

```bash
cd frontend
npm run api:generate
npm run check
```

Migration gate:

```bash
uv run alembic upgrade head
uv run alembic downgrade <previous_revision>
uv run alembic upgrade head
```

Exact database names and credentials belong to local/test environment configuration, not
to this document.

## Completion definition

Workspace collaboration strengthening is complete when all five implementation stages
have passed their exit gates and the canonical product behavior is summarized in
`docs/features/workspaces/README.md` and `src/app/features/workspaces/README.md`.

Completion does not imply realtime collaboration, comments, assignments, custom roles,
large-team pagination or PostgreSQL RLS. Those remain new product decisions, not hidden
tail work of this plan.
