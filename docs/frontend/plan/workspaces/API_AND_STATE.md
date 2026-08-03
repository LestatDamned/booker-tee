# Workspaces API and state boundary

Статус: target accepted 2026-08-03 in ADR-0006; Slice 1 directory/create/select
implemented and production-gated. Later endpoint groups remain proposed.

## Current boundary

- `src/app/api/v1/workspaces/router.py` implements `GET/POST
  /api/v1/workspaces` and `POST /api/v1/workspaces/{id}/select`.
- `frontend/app/routes/workspaces.tsx` owns canonical `/app/workspaces` and
  composes the feature in `frontend/app/features/workspaces/`.
- `/api/v1/session` returns only current user/workspace/membership/capabilities
  and CSRF token (`api/v1/session/responses.py`).
- React route loaders independently fetch session and feature snapshots in
  parallel. There is no global cache library.
- Browser session ownership is `UserSession.current_workspace_id`; Chat
  selection is a separate binding and must not be silently changed by web
  switch.

## Application actors

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

The first three actors are implemented in
`src/app/features/workspaces/application/{directory,creation,switching}.py`.
Settings/member/invitation actors below are proposals for later slices.

Application actors own transaction/locks/audit. Repositories keep visible
workspace predicates and persistence only. Public invitation preview is a
separate credential boundary, not an ordinary workspace read.

## Canonical routes

| Browser route | Ownership |
| --- | --- |
| `/app/workspaces` | React directory/create/switch |
| `/app/workspaces/:workspaceId/settings` | React authenticated settings/access/activity after its gate |
| `/workspaces?...` | Historical query-preserving 307 only after full directory replacement |
| `/workspaces/invitations/:token` | Kept public bridge initially per D11 |

Конкретная форма settings sections остаётся implementation detail Slice 2;
canonical directory/settings split принят в D2–D3.
Do not create routes for members/invites until D3 decides sections vs subroutes.

## Versioned JSON endpoints

### Directory and switch

These three endpoints are implemented in Slice 1. Settings, members and
invitations tables remain proposed contracts.

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
capabilities: canCreate
workspaceTypeOptions[]
currencyOptions[]
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

## Accepted deactivate transaction contract

This is the accepted D12 target, not current runtime behavior. Today there is no
workspace lifecycle actor or route. The affected persistence fields and readers
are factual references from `workspaces/models.py`, `users/models.py`,
`chat_integrations/models.py`, `chat_integrations/use_cases/workspace.py` and
`imports/documents/commands/upload.py`.

One `WorkspaceLifecycleService.deactivate(...)` transaction must lock the
workspace first and apply this database state:

| Consumer/state | Deactivate result | Restore result |
| --- | --- | --- |
| `Workspace.is_active`, `archived_at` | `false`, committed timestamp | `true`, clear `archived_at` after stale-token check |
| Pending `WorkspaceInvitation` | transition to `revoked`, set `revoked_at`; credentials never become valid again | remain revoked |
| `UserSession.current_workspace_id` pointing here | replace with deterministic active-membership fallback; set `NULL` only for an explicit no-workspace recovery outcome | do not switch sessions back automatically |
| `IntegrationConnection.status` | `disabled` | remain disabled until an explicit reconnect/reactivate action |
| `ChatConversationBinding.is_active` | `false` | remain disabled until explicitly re-enabled |
| `ChatIdentityBinding.is_active` | `false` | remain disabled; user explicitly binds/selects again |
| Unconsumed `ChatConversationState` | set `consumed_at` to lifecycle timestamp; payload retained for audit/debug policy | never reopen |
| Pending `IntegrationEventDelivery` | mark terminal `failed` with a bounded non-sensitive lifecycle reason before any later retry can send | never retry automatically |
| Memberships and roles | preserve unchanged | become usable again subject to active status |
| Accounts, documents/files, parse attempts/raw rows, rules, operations/money entries, categories, properties, audit | preserve unchanged | visible again through normal scoped readers |

The lifecycle response returns the committed fallback session snapshot and
impact counts only; it does not return member identities, invitation secrets,
Chat external IDs or integration credentials.

### In-flight boundary

- New authenticated/API/Chat work is denied because active context resolution
  already joins `Workspace.is_active`; lifecycle implementation must retain this
  server-side check.
- Financial, membership, invitation and settings mutations must lock/recheck the
  workspace immediately before their commit. A request that loses the race to
  deactivate returns a stable lifecycle conflict and cannot commit its mutation.
- Statement upload currently commits document metadata and a running parse
  attempt before synchronous extraction. If deactivate wins after either
  preservation commit, parsing may finish only the raw/document/attempt
  preservation path. It must skip confirmation, rules side effects and external
  notifications; stored files and extracted raw data are not deleted.
- Chat notification delivery currently performs the external provider call
  synchronously before its database commit. An already-issued external message
  cannot be rolled back. Deactivation must prevent new dispatch selection and
  terminalize persisted pending deliveries, but the product cannot promise
  recall of a provider call already in progress. This limitation must be named
  in implementation tests and operational copy rather than hidden behind an
  impossible atomicity claim.

### Lock order

To avoid cross-feature deadlocks, lifecycle-aware mutations use the same order:

```text
Workspace row
-> affected UserSession / WorkspaceMember / WorkspaceInvitation rows
-> IntegrationConnection / Chat bindings and states
-> feature aggregate rows
-> audit event
-> one commit
```

Repositories expose bounded lock/update queries; the application actor owns the
order, transaction and audit. No generic CRUD or event bus is introduced for
this slice.
