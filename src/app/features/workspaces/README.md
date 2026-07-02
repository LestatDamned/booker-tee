# Users and workspaces production plan

This document is the implementation plan for making `users` and `workspaces`
production-ready enough for private server use, shared workspaces, and a future
Telegram bot entry point.

`docs/domain/DOMAIN_MODEL.md` remains the canonical product/domain source of truth. This file
keeps the local module contract concrete for day-to-day implementation.

## Product goal

Users and workspaces are the security and collaboration foundation of Booker Tee.

Target behavior:

```text
user registers or logs in
-> user has one or more workspace memberships
-> user chooses current workspace
-> every financial action runs inside WorkspaceContext
-> permissions are checked from the active WorkspaceMember
```

The workspace boundary must be strong before Telegram integration is added. The
bot must reuse the same user, membership, role, and workspace checks as the web
application.

## Architecture story

Read the module as one story.

```text
Who is this person?
-> users resolves User from credentials, session, or external identity
-> workspaces finds an active WorkspaceMember
-> workspaces builds WorkspaceContext
-> feature services receive WorkspaceContext
-> repositories query only inside context.workspace.id
-> permissions decide whether the action is allowed
```

Every request should be easy to trace through that story. If a route cannot
explain which user, workspace, membership, and permission it uses, the route is
not ready.

### Signup story

```text
POST /signup
-> UserService validates identity input
-> AuthenticationService creates User
-> WorkspaceService creates personal Workspace
-> WorkspaceService creates owner WorkspaceMember
-> AuthenticationService creates UserSession
-> one transaction commits the whole result
```

The personal workspace is not a convenience side effect. It is part of the
registration use case.

### Login story

```text
POST /login
-> AuthenticationService verifies email and password
-> WorkspaceService chooses an active membership
-> AuthenticationService creates UserSession with current_workspace_id
-> UI enters the selected workspace
```

If the last selected workspace is unavailable, the service must choose another
active membership or fail clearly.

### Financial request story

```text
GET /accounts
-> get_current_workspace_context resolves UserSession
-> WorkspaceService verifies active membership
-> permissions allow read access
-> AccountService lists accounts by workspace_id
```

Financial feature modules should not know how login works. They receive
`WorkspaceContext` and trust it as the already-checked access boundary.

### Invitation story

```text
owner/admin creates a one-time invite link
-> WorkspaceInvitation stores token_hash, role, expiry, and status
-> invited person receives the link through any trusted channel
-> invited person logs in or signs up
-> invitation is accepted once from an authenticated session
-> active WorkspaceMember is created
-> user can switch to the shared workspace
```

Invitation is not email. Email, Telegram, QR, or manual sharing are delivery
channels. The first production slice uses a one-time link because it is simple,
safe, and does not require SMTP infrastructure. Invitation tokens are
credentials: store only hashes, expire them, allow revocation, and never reuse
them.

### Telegram story

```text
/start in Telegram
-> ExternalIdentity resolves or links User
-> service selects an active workspace membership
-> bot commands build the same WorkspaceContext
-> financial services run unchanged
```

Telegram is another door into the same house, not a second authorization system.

## Architecture postulates

1. Identity is not ownership.
   `User` identifies a person. `Workspace` owns financial data.

2. Membership is access.
   A user can touch a workspace only through an active `WorkspaceMember`.

3. Context is the border.
   `WorkspaceContext` must contain the current user, workspace, and membership.
   Feature services receive context instead of separate primitive ids.

4. Repositories do not decide.
   Repositories perform queries and persistence. They do not choose roles,
   create side effects, or silently repair data.

5. Services tell the story.
   Business actions live in service methods named after use cases:
   `register_user`, `create_workspace`, `invite_member`,
   `accept_invitation`, `switch_workspace`.

6. Routers are translators.
   Routers translate HTTP forms and requests into commands, call services, and
   return responses. They do not contain business rules.

7. Permissions are reusable functions.
   Role checks live in `permissions.py`, not inside templates, routers, or
   individual services.

8. One use case, one transaction boundary.
   A high-level service action should commit once. Partial commits inside helper
   methods make auth and workspace state hard to reason about.

9. No silent fallback across workspaces.
   If access is missing, fail clearly. Do not switch workspaces or create data in
   another workspace without an explicit service decision.

10. External channels reuse the same core.
    Web, Telegram, and future APIs must all resolve the same user, workspace,
    membership, and permission checks before calling financial services.

## Permission core

Workspace access is intentionally small and explicit:

```text
viewer   -> read workspace only
analyst  -> read workspace only
uploader -> read workspace, manage imports
editor   -> read workspace, write financial data, manage imports
admin    -> editor permissions plus member invitations
owner    -> admin permissions plus workspace settings
```

Financial write routes must depend on `require_financial_write_context`.
Import mutation routes must depend on `require_import_management_context`.
Member invitation routes must depend on `require_member_management_context`.
Workspace settings routes must depend on `require_workspace_management_context`.

The service layer may repeat important checks. Dependency checks give fast
HTTP-level rejection; service checks keep use cases safe for Telegram and other
non-web entry points.

Member management has extra safety rules:

```text
do not assign owner through member management
do not let a user change their own role
do not let a user disable their own access
do not disable the last active owner
admin manages regular members only
owner can manage non-owner members
```

## Code should read like a story

The implementation should be readable top to bottom. A developer should be able
to open one use-case file and understand the action without jumping through ten
generic helpers.

Working code is not enough. The code is ready only when it is understandable,
reusable, and extendable at the same time. It should guide the reader by hand:
first identity, then membership, then permission, then the business action, then
persistence. A programmer who has never seen this module should be able to read
the main use case and retell what happens in product language.

Quality bar:

- The happy path is visible.
- Guards and permission checks have names.
- Side effects happen in obvious places.
- Domain words are used instead of generic technical words.
- Reusable rules are extracted once and imported where needed.
- Extension points are explicit, not hidden in conditionals.
- Tests describe the same story as the code.

Good code shape:

```python
async def invite_member(command: InviteMemberCommand) -> WorkspaceInvitation:
    actor = await memberships.require_active_member(command.actor_user_id, command.workspace_id)
    ensure_can_invite_members(actor)

    invitation = await invitations.create_pending_invitation(command)
    await session.commit()
    return invitation
```

Bad code shape:

```python
async def handle(data: dict[str, Any]) -> Any:
    user = await get_user(data)
    result = await process_workspace(user, data, mode="invite")
    await finalize(result)
    return result
```

Prefer:

- domain nouns over generic words;
- explicit command objects over loose dictionaries;
- early returns over deep nesting;
- use-case names over technical action names;
- one visible happy path with named guard checks.

## File size and split rules

Large files make the story disappear. Split by responsibility before files become
hard to scan.

Soft limits:

```text
models.py          can be larger, but only persistence definitions
repository.py      about 150-220 lines per focused repository
service.py         about 150-220 lines before extracting use cases
router.py          about 150-220 lines before splitting route groups
permissions.py     small, pure role/capability checks
commands.py        small dataclasses/Pydantic command objects
```

When `service.py` grows, split by story:

```text
workspaces/application/
  registration.py      create personal workspace for a new user
  context.py           resolve WorkspaceContext
  workspace_management.py
  member_management.py
  invitations.py
  telegram_links.py
```

When `repository.py` grows, split by aggregate:

```text
workspaces/repositories/
  workspaces.py
  memberships.py
  invitations.py
```

When `router.py` grows, split by UI/API surface:

```text
workspaces/routes/
  workspaces.py
  members.py
  invitations.py
```

The split is worth it when a file has more than one story. Do not split only to
look architectural; split when naming a smaller file makes the code easier to
read.

## Function shape rules

- Keep public service methods named as use cases.
- Keep private helpers short and named by intention.
- Avoid boolean flag parameters; create two functions instead.
- Avoid broad `data`, `payload`, `result`, `item`, and `obj` names when a domain
  name exists.
- Do not pass separate `user_id`, `workspace_id`, and `role` through several
  layers when `WorkspaceContext` is available.
- Do not hide permission checks inside repositories.
- Do not make templates decide business rules.

## Reuse rules

Prefer small reusable functions when the rule is stable and named in domain
language.

Good reusable functions:

```text
normalize_email
clean_user_name
validate_password
clean_workspace_name
normalize_currency
ensure_can_invite_members
ensure_can_manage_workspace
ensure_can_write_finance
ensure_last_owner_is_preserved
```

Avoid generic helpers with unclear ownership:

```text
validate_data
check_access
process_user
handle_workspace
```

The best reusable function should read like a sentence from the product domain.

## Module boundaries

`users` owns identity:

- user profile fields;
- password authentication;
- web sessions;
- external identity links such as Telegram later;
- login, logout, registration, session resolution.

`workspaces` owns financial access:

- workspaces;
- workspace members;
- workspace invitations;
- current workspace context;
- roles and permissions;
- membership checks for all workspace-owned data.

Financial data must never be owned directly by `User`. Use user ids only for
audit fields such as `created_by_user_id`, `uploaded_by_user_id`, or
`updated_by_user_id`.

## Target files

```text
src/app/features/users/
  models.py          User, UserSession, ExternalIdentity
  repository.py      user/session/external identity queries only
  service.py         registration, login, logout, session resolution
  router.py          signup, login, logout, profile
  errors.py

src/app/features/workspaces/
  models.py          Workspace, WorkspaceMember, WorkspaceInvitation
  repository.py      workspace/member/invitation queries only
  service.py         workspace CRUD, membership, invitation flow
  permissions.py     role and capability checks
  dependencies.py    current WorkspaceContext dependency
  router.py          workspace UI routes
  commands.py        command DTOs for service input
  errors.py
```

Layer rule:

```text
Router -> Service -> Repository -> Model
```

Repositories do database queries and `flush`. Services own business rules and
transaction boundaries. Routers parse requests, call services, render templates,
and redirect.

## Data model target

Already present:

- `User`
- `UserSession`
- `Workspace`
- `WorkspaceMember`

Add for shared workspace production readiness:

- `WorkspaceInvitation`
- `ExternalIdentity` for Telegram and future integrations

Recommended `WorkspaceInvitation` fields:

```text
id
workspace_id
email
role
token_hash
status              pending | accepted | revoked | expired
expires_at
accepted_at
revoked_at
invited_by_user_id
accepted_by_user_id
created_at
updated_at
```

Recommended `ExternalIdentity` fields:

```text
id
user_id
provider            telegram
provider_user_id
provider_chat_id
display_name
is_active
created_at
updated_at
last_seen_at
```

Unique constraints:

```text
users.email
workspace_members(workspace_id, user_id)
workspace_invitations(token_hash)
external_identities(provider, provider_user_id)
```

## Roles

Initial roles should stay simple and stable:

```text
owner
admin
editor
uploader
analyst
viewer
```

Recommended capability matrix:

```text
owner    manage workspace, members, invitations, all finance actions
admin    manage members except owners, invitations, all finance actions
editor   create/edit accounts, imports, operations, categories, properties
uploader upload documents and work import review
analyst  read reports and financial data
viewer   read-only access
```

Rules:

- A workspace must always have at least one active owner.
- Only owner can archive/delete a workspace.
- Only owner/admin can invite members.
- A member cannot grant a role with more power than their own role.
- Disabled/removed members cannot access the workspace.

## WorkspaceContext

Target context:

```python
WorkspaceContext(
    user=user,
    workspace=workspace,
    membership=membership,
)
```

All workspace-owned features must receive this context and query by
`context.workspace.id`.

Bad:

```python
select(Account).where(Account.id == account_id)
```

Good:

```python
select(Account).where(
    Account.id == account_id,
    Account.workspace_id == context.workspace.id,
)
```

## Implementation plan

### Phase 1: session and workspace foundation

- Make registration atomic: `User + personal Workspace + owner WorkspaceMember + UserSession`.
- Keep exactly one commit per high-level use case.
- Remove duplicate personal workspace creation logic.
- Ensure login creates or repairs current workspace only through active membership.
- Ensure logout revokes `UserSession` and clears the cookie.

Acceptance:

- Signup creates a user, personal workspace, owner membership, and session.
- Login selects an accessible workspace.
- Expired/revoked sessions cannot access financial pages.

### Phase 2: membership-aware context

- Extend `WorkspaceContext` with active `WorkspaceMember`.
- Add repository/service methods for active membership checks.
- Route all workspace switching through membership checks.
- Add `permissions.py` with role/capability helpers.

Acceptance:

- A user cannot switch to a workspace without active membership.
- A disabled member loses access immediately.
- Every financial route depends on membership-backed `WorkspaceContext`.

### Phase 3: workspace management

- Keep create/list/update workspace flows.
- Add member list page for a workspace.
- Add role update and member disable/remove actions.
- Protect owner-only and admin-only actions with permission helpers.

Acceptance:

- Owner can manage workspace settings and members.
- Non-owner cannot edit protected workspace settings.
- Last active owner cannot be removed or downgraded.

### Phase 4: invitations

- Add `WorkspaceInvitation` model and migration.
- Add invitation service: create, revoke, accept.
- Store only token hashes in the database.
- Support accepting an invitation after login or after signup.

Acceptance:

- Owner/admin can invite by email.
- Invitation token is one-time and expires.
- Accepted invitation creates active membership.
- Revoked/expired/used token cannot be reused.

### Phase 5: Telegram readiness

- Add `ExternalIdentity` model and migration.
- Add service methods to link and unlink Telegram identity.
- Store Telegram identity separately from financial data.
- Telegram commands must resolve the same user and workspace membership as web.

Acceptance:

- Telegram identity links to an existing user.
- Telegram actions fail if no active workspace membership exists.
- Telegram-created records use the same `created_by_user_id` and workspace checks.

## Server readiness

Users and workspaces are safe to expose on a private server only when runtime
settings make the deployment boundary explicit.

Required production environment:

```text
BOOKER_TEE_ENVIRONMENT=production
BOOKER_TEE_AUTH_SECRET_KEY=<strong random secret, 32+ chars>
BOOKER_TEE_SESSION_COOKIE_SECURE=true
BOOKER_TEE_ALLOWED_HOSTS=<domain>,<reverse-proxy-host-if-needed>
```

Runtime guardrails:

- production startup rejects the local auth secret;
- production startup rejects insecure session cookies;
- production startup rejects missing or wildcard allowed hosts;
- session cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` in production;
- `TrustedHostMiddleware` rejects unexpected Host headers;
- security headers are added to responses by default.

This protects the collaboration layer before Telegram is added. Telegram must
reuse the same production settings, user resolution, workspace membership checks,
and permission functions as the web app.

## Test plan

Business-critical tests:

- signup creates `User`, `Workspace`, `WorkspaceMember(owner, active)`, `UserSession`;
- duplicate email is rejected;
- login creates session for active user;
- inactive user cannot log in;
- logout revokes session;
- current workspace cannot be a workspace without active membership;
- workspace creation creates owner membership;
- workspace switching rejects inaccessible workspace;
- owner/admin can invite, viewer cannot;
- invitation accept creates membership;
- invitation token cannot be reused;
- disabled member cannot access financial routes;
- role permissions protect mutation routes;
- last owner cannot be removed or downgraded.

Run before considering the module production-ready:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest tests/test_users_workspaces.py
uv run pytest
```

## Explicit non-goals for this phase

- Complex enterprise RBAC.
- Organization billing.
- Public SaaS signup hardening.
- Fine-grained per-account permissions.
- Full audit log UI.
- Telegram operation UX.

Telegram can start after identity, memberships, roles, and invitations are
reliable.
