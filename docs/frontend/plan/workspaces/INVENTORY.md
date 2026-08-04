# Workspaces factual inventory

Статус: audit snapshot 2026-08-02. Разделы «Предложение» не описывают текущий
runtime.

## Route inventory

Все зарегистрированные routes подтверждены read-only introspection
`create_app().routes` и `src/app/features/workspaces/router.py`.

| Method/path | Current behavior | Authority and redirect |
| --- | --- | --- |
| `GET /workspaces` | Full Jinja directory/settings page | Auth via `get_current_workspace_context`; no query contract; 200 |
| `POST /workspaces` | Creates workspace and owner membership, then selects it | Any authenticated active member; CSRF; 303 `/workspaces` |
| `POST /workspaces/{workspace_id}` | Updates name/type/default currency | Current context must be owner; target may be another active workspace owned by actor; 303 `/workspaces` |
| `POST /workspaces/{workspace_id}/select` | Changes `UserSession.current_workspace_id` | Server verifies active membership; form `next`; safe local 303 |
| `POST /workspaces/{workspace_id}/invitations` | Creates one-time link and rerenders page | Current workspace only; owner/admin; role form; 201 HTML |
| `POST /workspaces/{workspace_id}/invitations/{invitation_id}/revoke` | Marks pending invite revoked | Current workspace only; owner/admin; 303 `/workspaces` |
| `POST /workspaces/{workspace_id}/members/{member_id}/role` | Changes non-owner member role | Current workspace only; owner/admin policy; 303 `/workspaces` |
| `POST /workspaces/{workspace_id}/members/{member_id}/disable` | Sets non-owner membership disabled | Current workspace only; self/owner guards; workspace, actor and target rows locked; 303 |
| `POST /workspaces/{workspace_id}/members/{member_id}/reactivate` | Sets membership active | Current workspace only; owner/admin policy; 303 |
| `GET /workspaces/invitations/{invitation_token}` | Public/optional-auth preview | Token hash lookup; renders valid/error page; no redirect |
| `POST /workspaces/invitations/{invitation_token}/accept` | Consumes invite, creates/reuses membership, switches session | Auth + CSRF; 303 `/dashboard` |

`workspace_id`, `member_id`, `invitation_id` — UUID path parameters. Directory
does not consume query parameters. Switch accepts form field `next`; login and
signup accept query/form `next`. Guards in `safe_workspace_return_path()` and
`users.router.safe_next_path()` reject external and protocol-relative URLs but
allow any same-origin absolute path.

### Deep links and anchors

- Workspace, member, invitation and audit cards have stable SSR anchors
  `#workspace-{id}`, `#workspace-member-{id}`,
  `#workspace-invitation-{id}`, `#workspace-audit-{id}` from
  `presentation/presenter.py`.
- There is no GET detail/settings route by workspace ID; anchors are the only
  direct in-page identity.
- Mutation redirects do not preserve row anchors or success state.
- Invitation token is a credential in the URL path and is also preserved in
  login/signup `next`.

## Entry and exit links

| Consumer | Current transition |
| --- | --- |
| React AppShell desktop/mobile | workspace card -> `/workspaces`; profile -> `/users` (`frontend/app/shell/app-shell.tsx`) |
| Legacy base shell | context strip and nav -> `/workspaces` (`templates/base.html`) |
| Profile | toolbar -> `/workspaces` (`templates/users/index.html`) |
| Dashboard/onboarding | first-step link -> `/workspaces` (`templates/components/onboarding_checklist.html`) |
| Public home | setup quick action -> `/workspaces` when authenticated (`templates/home.html`) |
| Accounts/imports/ledger/reports/properties/categories/rules | no feature-local workspace route; current context is reached through React or legacy AppShell |
| Invitation preview | `/workspaces`, `/login?next=...`, `/signup?next=...` |
| Invitation accept | `/dashboard`; current workspace becomes invited workspace |
| Chat | separate button-first workspace selector; no browser route required (`chat_integrations/use_cases/workspace.py`) |

There is currently no historical redirect for `/workspaces`: it is still the
live SSR route and is intentionally absent from `legacy_frontend_redirects.py`.

## SSR, HTMX, Alpine, JavaScript and CSS

- `templates/workspaces/index.html` owns summary, access, invitations,
  directory/create and audit sections.
- `_workspace_card.html` owns select and inline settings edit.
- `accept_invitation.html` owns public/optional-auth preview and authenticated
  accept form.
- `_action.html` renders POST forms, panel toggles and `hx-confirm` attributes.
- Alpine is used directly only for copy-link feedback on the invitation panel;
  `base.html` also uses Alpine for mobile navigation.
- No workspace-specific `hx-post`, `hx-get` or fragment response exists. Forms
  are ordinary full-page POSTs. `hx-confirm` is present, but there is no browser
  test proving confirmation for a non-HTMX form; treat this as unverified.
- `entity-target.js` is loaded globally, but workspace cards do not set its
  `data-entity-working` marker. It can clear URL hashes after interactive clicks.
- Workspace-specific CSS lives in `static/css/app.css` selectors
  `.workspace-section*`, `.workspace-create*`, `.workspace-card*`,
  `.workspace-form*`, `.workspace-member*`, `.workspace-invitation*`,
  `.workspace-audit*`, plus shared `.entity-card`, `.financial-row`,
  `.row-actions`, `.form-panel`, `.summary-grid`.

## Current rendered states

### Success/empty/loading

- Directory is a full document response; there is no explicit loading or
  pending state and no double-submit prevention.
- Auth/session resolution silently chooses another active membership or creates
  a personal workspace if none exists, so a durable “no workspace” state is
  normally hidden (`AuthenticationService._resolve_login_session_record`).
- Template still has an empty directory message and opens create details when
  `workspaces` is empty, but normal session resolution makes it difficult to
  reach.
- Create invitation is the only mutation that rerenders with an in-context
  success panel and one-time link. Other successes redirect silently.

### Errors/forbidden/stale

- Create invitation errors rerender `index.html` with 400 and an inline notice.
- Invalid invitation preview renders its own error state with 200.
- Create/update/switch/member/revoke/accept failures mostly become raw FastAPI
  `HTTPException` JSON/HTML responses rather than a prepared workspace page.
- Permission dependencies return 403 with a Russian detail. There is no
  workflow-specific forbidden page.
- No optimistic token or stale-state recovery exists for workspace/member/
  invitation mutations.
- Session API/React shell has route loading, unauthenticated and generic error
  states, but no Workspaces React route exists.

## Persistence and relationships

`src/app/features/workspaces/models.py`:

- `Workspace`: `owner_id`, optional unique slug, type, default currency,
  `is_active`, timestamps, `archived_at` and relationships to members, invites,
  audit, accounts, imports, operations, money entries, categories, properties
  and transaction rules.
- `WorkspaceMember`: unique `(workspace_id, user_id)`, role, status,
  inviter/joined/timestamps.
- `WorkspaceInvitation`: unique token hash, workspace, role/status, inviter,
  accepter and expiry/accepted/revoked timestamps.
- `WorkspaceAuditEvent`: workspace, actor/target, event type, entity identity
  and JSON details.
- `UserSession.current_workspace_id` uses `ON DELETE SET NULL`
  (`features/users/models.py`). Many workspace-owned aggregates cascade with
  workspace deletion; PostgreSQL characterization already contains a direct
  delete test in `tests/features/transaction_rules/test_rule_delete_postgres.py`.

No workspace/member/invitation version column exists. `updated_at` exists on
workspace/member/invitation and can be the proposed optimistic token.

## Repository and service flows

### Reads

- Active membership queries join `Workspace` and require member `ACTIVE` plus
  workspace `is_active=true`.
- Member, pending invite and audit list queries are scoped by workspace ID.
- Token preview is intentionally global by token hash and eager-loads the
  workspace; token is the bearer credential.
- `list_members_for_workspace` includes all statuses; pending invitations list
  includes only `PENDING`; activity is bounded to 20.

### Mutations and transaction ownership

- Repository creates and flushes; `WorkspaceService` and
  `AuthenticationService` commit high-level actions.
- Signup atomically creates User + personal Workspace + owner Membership +
  UserSession and commits once.
- Workspace create commits once, then router calls session switch, which commits
  a second transaction. A failure between them leaves a created but not selected
  workspace.
- Invitation create/accept/revoke, role/status change and settings update each
  commit once with their audit event.
- No explicit rollback is called; AsyncSession request cleanup is relied upon
  for uncommitted failures.
- `resolve_login_session()` updates `last_seen_at` and commits on every
  successful resolution. Thus API/SSR reads are not side-effect free.
- Expired invitation preview marks `EXPIRED` and commits during GET.

## Permission facts

Current matrix from `permissions.py` and
`tests/features/workspaces/test_workspace_permissions.py`:

| Role | Read | Financial write | Imports | Members/invites | Settings |
| --- | --- | --- | --- | --- | --- |
| owner | yes | yes | yes | yes | yes |
| admin | yes | yes | yes | yes | no |
| editor | yes | yes | yes | no | no |
| uploader | yes | no | yes | no | no |
| analyst | yes | no | no | no | no |
| viewer | yes | no | no | no | no |

Additional facts:

- Owner role cannot be assigned through invitation or ordinary role edit.
- User cannot edit own role or disable own access.
- Admin can manage editor/uploader/analyst/viewer, but not owner/admin.
- Owner can manage any non-owner. Since Slice 3, legacy member mutations lock
  workspace/actor/target in the same order as the API and owner disable is
  rejected in favour of explicit ownership transfer.
- `Workspace.owner_id` is separately checked for settings update.

## Confirmed security/isolation findings

Severity expresses migration risk, not an assertion that exploitation has
already happened.

Authenticated unsafe SSR routes уже защищены form-token CSRF проверкой:
`get_current_workspace_context()` вызывает `verify_request_csrf()` до session
resolution для каждого метода вне `GET/HEAD/OPTIONS/TRACE`. Все текущие
authenticated workspace POST handlers зависят от этого context напрямую или
через permission dependencies. Пробел относится к route-level regression
coverage, а не к отсутствию runtime guard (`dependencies.py`, `router.py`).

1. **High — concurrent invitation replay is not serialized.** Token lookup is
   not locked and status is checked before create/commit. Two users can race a
   pending token. Real PostgreSQL barriers prove two accepts both commit and
   create two active memberships; accept and revoke also both commit
   (`service.accept_invitation`, `service.revoke_invitation`,
   `test_workspace_concurrency_postgres.py`).
2. **Resolved in Slice 3 — legacy last-owner count-then-write was race-prone.**
   The audit's PostgreSQL barrier proved both old service calls could commit and
   leave zero active owners. Production legacy mutations now serialize on the
   workspace and cannot disable an owner; the new transfer actor locks all
   memberships and verifies one owner matching `Workspace.owner_id`
   (`service.disable_member`, `test_workspace_concurrency_postgres.py`).
3. **High — hard delete blast radius is real and has no product guard.** FK
   cascades reach workspace-owned data; no delete route currently exists, which
   must remain true until an explicit operational policy.
4. **Medium — read paths commit.** Session resolution and expired invitation
   preview mutate state on GET. This violates current architecture’s
   side-effect-free read target and complicates retry/cache reasoning.
5. **Partly resolved — invitation transitions have no stale protection.**
   Settings, member role/status, transfer and leave now validate authoritative
   timestamps. Legacy invitation revoke/accept remain last-write-wins.
6. **Partly resolved — invitation create is not idempotent.** React workspace
   create has `Idempotency-Key`/fingerprint protection; legacy invitation retry
   can still create multiple invitations.
7. **Resolved Slice 6 — deactivation consequence was undefined.**
   `WorkspaceLifecycleService` now owns the locked session/invitation/
   integration/Chat transaction; unsafe request and import completion boundaries
   recheck the active workspace. Restore does not resurrect revoked runtime.
8. **Medium — invitation token is present in URL/history and login return.** It
   is high entropy and stored only as hash, but no explicit no-store/referrer
   response contract is present.
9. **Partly resolved UX-security — invitation revoke confirmation is
   unproven.** React disable/transfer/leave use tested semantic dialogs. The
   retained SSR revoke still relies on the legacy `hx-confirm` composition.
10. **Coverage gap — invitation route masking remains.** React settings,
    members and ownership now have API masking/CSRF contracts; retained public
    and authenticated invitation routes still need the Slice 4–5 matrix.

## Clean-database migration blocker found during browser isolation — resolved

Creating the disposable browser database exposed a repository-wide portability
defect outside the Workspaces runtime: `alembic upgrade head` from an empty
PostgreSQL database failed at
`migrations/versions/20260722_0017_confirmed_raw_dedupe_guard.py` with
`UnsafeNewEnumValueUsageError`. The partial index predicate uses
`raw_transaction_status = 'confirmed'` in the same Alembic transaction in which
an earlier revision added that enum value. PostgreSQL requires the enum change
to be committed before use.

Resolved 2026-08-03 in
`migrations/versions/20260613_0003_phase4_ledger_posting.py` and
`migrations/versions/20260613_0004_phase5_dedup_reparse.py`: both PostgreSQL enum
additions use Alembic `autocommit_block`, making the values visible to later
revisions in a full-chain run. A clean disposable PostgreSQL database reached
`20260802_0021`; SQL inspection confirmed `confirmed`, `possible_duplicate` and
`uq_raw_transactions_workspace_confirmed_dedupe_hash`. The disposable database
also passed `head -> 20260720_0016 -> head`.

## Existing tests and consumers

- Workspace tests cover permission matrix, invitation hashing/expiry/basic
  acceptance, self-role guard, admin escalation guard, last-owner sequential
  guard and a legacy template permission assertion.
- User tests cover signup transaction, local return path and CSRF primitives.
- Session API tests cover response/capabilities and API CSRF infrastructure.
- Chat tests cover active membership resolution and workspace switching flows.
- No Workspaces React/API/component/browser replacement tests exist.

Named non-browser/domain consumers to preserve:

- `AuthenticationService` signup/login/session/switch;
- all financial API/SSR dependencies using `WorkspaceContext`;
- Chat identity binding, resolver and switcher;
- transaction-rule seeding workspace lock;
- persistence relationships/migrations and workspace-scoped repositories across
  Accounts, Imports, Ledger, Reports, Categories, Properties and Rules.
