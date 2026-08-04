# Workspaces API and state boundary

Статус: target accepted 2026-08-03 in ADR-0006; Slice 1–5 production-gated
2026-08-04. Lifecycle endpoint group remains proposed; public invitation
preview/accept is the retained minimal SSR bridge over the Slice 5 actor.

## Current boundary

- `src/app/api/v1/workspaces/router.py` implements directory/create/select,
  target settings, members, ownership, self-leave and authenticated invitation
  administration endpoints.
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
  list / change_role / disable / reactivate

WorkspaceOwnershipService
  leave / transfer_ownership

WorkspaceInvitationService
  read / create / revoke

WorkspaceService (retained public bridge only)
  preview_credential / accept_credential
```

Directory, creation, switching, settings, member management, ownership/leave
and invitation administration are implemented in
`src/app/features/workspaces/application/`. Lifecycle remains proposed.

Application actors own transaction/locks/audit. Repositories keep visible
workspace predicates and persistence only. Public invitation preview is a
separate credential boundary, not an ordinary workspace read.

## Canonical routes

| Browser route | Ownership |
| --- | --- |
| `/app/workspaces` | React directory/create/switch |
| `/app/workspaces/:workspaceId/settings` | React general settings, members, invitations and lifecycle impact read model; activity remains later |
| `/workspaces?...` | Historical query-preserving 307 only after full directory replacement |
| `/workspaces/invitations/:token` | Kept public bridge initially per D11 |

Slice 2 uses a dedicated general settings page without a `section` query.
Do not create routes for members/invites until their slices choose sections vs
subroutes from measured content size.

## Versioned JSON endpoints

### Directory and switch

The directory endpoints are implemented in Slice 1, settings in Slice 2,
member/ownership rows in Slice 3 and invitations in Slice 4. Lifecycle mutation
rows remain proposed contracts.

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces` | User-accessible active/inactive workspace summaries, current identity, directory capabilities |
| `POST` | `/api/v1/workspaces` | Create with `Idempotency-Key`; return committed record + session snapshot if selected |
| `POST` | `/api/v1/workspaces/{id}/select` | Verify membership server-side; expected current ID; return committed session snapshot |

### Settings/lifecycle

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{id}` | **Implemented Slice 2:** mask absent/foreign workspace; identity, actor membership, capabilities, options and owner-only lifecycle counts |
| `PUT` | `/api/v1/workspaces/{id}` | **Implemented Slice 2:** owner-only name/type/currency + `expectedUpdatedAt`; committed settings snapshot |
| `POST` | `/api/v1/workspaces/{id}/deactivate` | Locked impact command, explicit confirmation payload |
| `POST` | `/api/v1/workspaces/{id}/restore` | Owner-only restore with stale token |

### Members/ownership

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{id}/members` | **Implemented:** bounded workspace-scoped member facts/capabilities |
| `PUT` | `/api/v1/workspaces/{id}/members/{memberId}/role` | **Implemented:** role + expected member timestamp |
| `POST` | `/api/v1/workspaces/{id}/members/{memberId}/disable` | **Implemented:** locked transition plus target session/Chat invalidation |
| `POST` | `/api/v1/workspaces/{id}/members/{memberId}/reactivate` | **Implemented:** locked membership transition; revoked Chat bindings are not silently restored |
| `POST` | `/api/v1/workspaces/{id}/leave` | **Implemented:** non-owner self-leave, stale member/current-session snapshots, deterministic fallback and hard reload |
| `POST` | `/api/v1/workspaces/{id}/transfer-ownership` | **Implemented:** workspace/member row locks, exact authoritative-owner invariant, atomic `owner_id` plus two-role transition |

### Invitations

| Method | Endpoint | Contract |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{id}/invitations` | **Implemented Slice 4:** bounded pending metadata and server capabilities; never token/hash |
| `POST` | `/api/v1/workspaces/{id}/invitations` | **Implemented Slice 4:** role + `Idempotency-Key`; returns transient share URL only in this response (and its safe replay) |
| `POST` | `/api/v1/workspaces/{id}/invitations/{invitationId}/revoke` | **Implemented Slice 4:** expected timestamp and locked transition |
| `GET` | `/workspaces/invitations/{token}` | **Implemented Slice 5:** minimal no-store/no-referrer SSR preview with bounded public facts |
| `POST` | `/workspaces/invitations/{token}/accept` | **Implemented Slice 5:** CSRF-protected atomic membership, invitation, audit and current-session transition |

Create derives the invitation row ID with `uuid5(workspace, actor, key)` and
the credential with stdlib HMAC over that ID. This makes an ambiguous retry
return the same credential without storing plaintext or adding a new table.
Reuse with another role or terminal invitation returns `idempotency_conflict`.
All invitation responses are `no-store`; list/revoke DTOs never contain the
credential or its hash.

The authenticated endpoints and minimal public credential boundary are
implemented. Public presentation intentionally remains SSR per D11; it has no
independent domain authority and success returns to canonical `/app/workspaces`.

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

### Settings response (implemented Slice 2)

```text
workspace facts + updatedAt
actor membership + server capabilities
workspaceTypeOptions + currencyOptions
lifecycle impact:
  financialHistoryPreserved=true
  active sessions count
  pending invitations count
  active chat connections/identity bindings count
```

Lifecycle counts are returned only to the authoritative owner; other active
members receive `lifecycleImpact: null`. Member summaries, invitation identity
and activity events are deliberately deferred to their own slices. Counts and
capabilities are server-owned. React does not infer update authority from role
strings or calculate lifecycle eligibility from visible rows.

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
- `409` reloads the authoritative record/member/session. The short three-field
  workspace settings form resets to that snapshot and asks for the edit again;
  longer create/member workflows preserve a draft where retry is meaningful.
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
