# Workspaces API and state boundary

Статус: proposal pending D1–D14. Current factual boundary is called out first.

## Current boundary

- There is no `/api/v1/workspaces` router.
- `/api/v1/session` returns only current user/workspace/membership/capabilities
  and CSRF token (`api/v1/session/responses.py`).
- React route loaders independently fetch session and feature snapshots in
  parallel. There is no global cache library.
- Browser session ownership is `UserSession.current_workspace_id`; Chat
  selection is a separate binding and must not be silently changed by web
  switch.

## Proposed application actors

Do not serialize the Jinja `WorkspacesPageVM` or expose ORM models.

```text
WorkspaceDirectoryReader
  read_for_user(user_id)

WorkspaceCreator
  create(actor, command, idempotency_key)

WorkspaceSessionSwitcher
  switch(user_session, target_id, expected_current_id)

WorkspaceSettingsReader / WorkspaceSettingsService
  read(actor, workspace_id)
  update(actor, workspace_id, command)
  deactivate / restore

WorkspaceMemberService
  list / change_role / disable / reactivate / leave / transfer_ownership

WorkspaceInvitationService
  list / create / revoke / preview_credential / accept_credential
```

Application actors own transaction/locks/audit. Repositories keep visible
workspace predicates and persistence only. Public invitation preview is a
separate credential boundary, not an ordinary workspace read.

## Proposed canonical routes

| Browser route | Ownership |
| --- | --- |
| `/app/workspaces` | React directory/create/switch |
| `/app/workspaces/:workspaceId/settings` | React authenticated settings/access/activity after its gate |
| `/workspaces?...` | Historical query-preserving 307 only after full directory replacement |
| `/workspaces/invitations/:token` | Kept public bridge initially per D11 |

Potential `section` URL values for settings are a proposal, not yet accepted.
Do not create routes for members/invites until D3 decides sections vs subroutes.

## Proposed versioned JSON endpoints

### Directory and switch

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces` | User-accessible active/inactive workspace summaries, current identity, directory capabilities |
| `POST` | `/api/v1/workspaces` | Create with `Idempotency-Key`; return committed record + session snapshot if selected |
| `POST` | `/api/v1/workspaces/{id}/select` | Verify membership server-side; expected current ID; return committed session snapshot |

### Settings/lifecycle

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{id}` | Mask absent/foreign workspace; settings/membership capabilities |
| `PUT` | `/api/v1/workspaces/{id}` | Name/type/currency + `expectedUpdatedAt` |
| `POST` | `/api/v1/workspaces/{id}/deactivate` | Locked impact command, explicit confirmation payload |
| `POST` | `/api/v1/workspaces/{id}/restore` | Owner-only restore with stale token |

### Members/ownership

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{id}/members` | Bounded workspace-scoped member facts/capabilities |
| `PUT` | `/api/v1/workspaces/{id}/members/{memberId}/role` | Role + expected member timestamp |
| `POST` | `/api/v1/workspaces/{id}/members/{memberId}/disable` | Locked membership transition |
| `POST` | `/api/v1/workspaces/{id}/members/{memberId}/reactivate` | Locked membership transition |
| `POST` | `/api/v1/workspaces/{id}/leave` | Self leave after D9 |
| `POST` | `/api/v1/workspaces/{id}/transfer-ownership` | Atomic owner transfer after D8 |

### Invitations

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{id}/invitations` | Pending metadata only; never token/hash |
| `POST` | `/api/v1/workspaces/{id}/invitations` | Role + Idempotency-Key; returns one transient share URL once |
| `POST` | `/api/v1/workspaces/{id}/invitations/{invitationId}/revoke` | Expected timestamp/status; locked transition |
| `GET/POST` | public credential boundary TBD | Preview/accept depends on D11 and public routing decision |

Endpoint names and split are proposed. Implementation should combine list
responses when measured page needs show fewer bounded requests without creating
a giant all-purpose DTO.

## Proposed DTO facts

### Directory response

```text
currentWorkspaceId
workspaceRevision/session snapshot identity
items[]:
  id, name, type, defaultCurrency
  isActive, archivedAt, updatedAt
  membership: role, status, updatedAt
  isCurrent
  capabilities:
    canSelect, canUpdate, canManageMembers, canInvite
    canLeave, canDeactivate, canRestore
  blockingReasonCodes[]
directoryCapabilities: canCreate
workspaceTypeOptions[]
```

Do not expose owner/member emails in directory unless the view needs them. Do
not expose slug until it has an active route contract.

### Settings response

```text
workspace facts + updatedAt
actor membership + server capabilities/reasons
bounded member summaries
bounded pending invitation metadata
bounded activity events (safe projected labels/facts, no arbitrary secrets)
lifecycle impact:
  active sessions count (if safe/useful)
  pending invitations count
  active chat/integration bindings count
```

Counts and capabilities are server-owned. React must not infer permission from
role strings or calculate last-owner/deactivation eligibility from visible rows.

### Mutation response

Return the smallest truthful committed consistency set:

- create/settings/member/invite: changed snapshot + affected capabilities;
- switch/leave/deactivate/accept: full `SessionApiResponse`-equivalent snapshot
  and `navigationOutcome` because workspace boundary changed;
- invite create: credential only in this response, never future reads.

## Proposed stable errors

```text
workspace_not_found                    404
workspace_forbidden                    403 (only where resource existence is already known)
workspace_validation_error             422 + fieldErrors
workspace_update_conflict              409
workspace_switch_conflict              409
workspace_lifecycle_conflict           409
workspace_deactivation_blocked         422 + reasonCodes
member_not_found                       404 (same for foreign)
member_role_conflict                    409
member_transition_blocked              422 + reasonCodes
ownership_transfer_conflict            409
last_owner_required                    422
invitation_not_found                   404 for authenticated list identity
invitation_conflict                     409
invitation_credential_invalid          400/410, one privacy-safe public shape
idempotency_conflict                    409
invalid_csrf                            403
```

Use the existing stable API error envelope (`app/api/errors.py`). Foreign and
absent member/invitation/workspace IDs must use indistinguishable shapes and
timing-insensitive queries as far as practical.

## State ownership

| State | Owner |
| --- | --- |
| route identity, settings section, directory filters/search/page | URL |
| current workspace, membership, capabilities, lifecycle, counts | server/API snapshot |
| route-loaded directory/settings/member/invite snapshots | loader state |
| create/settings/role drafts, panels, dialog, pending/error/focus | feature-local React |
| one-time invitation share credential | transient local state only until dismissal/navigation |
| financial data, ownership, last-owner, token validity | server only |
| labels, visual tones, action placement | React/UI Foundation |

No workspace IDs from URL/body are trusted. API context takes user/session from
cookie and validates actor membership/capability against every target ID.

## Switch and cache invalidation contract

Proposed sequence:

```text
user confirms switch if dirty state exists
-> POST select(expectedCurrentWorkspaceId)
-> server locks session, validates active membership, commits
-> response contains new session/workspace identity
-> discard all route data/drafts tied to old workspace
-> hard navigate/reload to safe `/app` or `/app/workspaces`
-> loaders fetch only the new workspace
```

A hard boundary navigation is recommended for the first slice because there is
no shared client cache to invalidate and it guarantees component memory is
destroyed. If later replaced by SPA revalidation, a single root session owner
and explicit invalidation protocol must first be implemented and tested.

Never preserve an old workspace entity deep link after switch. A safe return
allowlist may preserve only workspace-neutral collection routes proven to make
sense in the new boundary.

## Stale/conflict recovery

- Financial/workspace mutations are not optimistic.
- `409` reloads the authoritative record/member/session and preserves user
  draft where retry is meaningful.
- Transition conflicts (invite consumed, member already disabled, owner
  changed) show the new state and do not blindly retry.
- Create retries use the same Idempotency-Key and receive the original committed
  result or a stable conflict for changed payload.
- Server locks the relevant workspace/session/invitation/member rows for
  ownership, last-owner, accept/revoke, switch and lifecycle transitions.

## CSRF and credential privacy

- All unsafe versioned requests use `X-CSRF-Token` through existing API
  transport; same-origin cookies are never sufficient alone.
- Public invitation GET is no-store and does not mutate status. Expiry is
  computed on read or transitioned by a write/maintenance boundary.
- Accept/revoke performs compare-and-consume under lock.
- Token/hash is absent from logs, audit details, list DTOs, generated labels and
  analytics. The one-time share URL is never cached in loader state.

