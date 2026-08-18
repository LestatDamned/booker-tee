# Workspaces runtime contract

Workspaces are the strict ownership boundary for financial data. Every
workspace-owned read and write must use the authenticated `WorkspaceContext` or
an equally strict actor/target membership check. IDs from URLs, JSON, forms,
Chat or integrations are never authority by themselves.

## Runtime surfaces

- Canonical UI: `/app/workspaces` and
  `/app/workspaces/:workspaceId/settings` in `frontend/app/features/workspaces/`;
  public invitation UI: `/app/workspaces/invitation#token=...`.
- Authenticated API: `/api/v1/workspaces*` in
  `src/app/api/v1/workspaces/router.py`.
- Historical `GET /workspaces`: query-preserving redirect to React in
  `src/app/legacy_frontend_redirects.py`. Removed legacy POST routes are not
  redirected.
- Public invitation API: preview and accept in
  `src/app/api/v1/workspaces/router.py`; the bearer token is accepted only in
  JSON request bodies and is never part of an HTTP path or query.

## Ownership and authority

- The server returns capabilities and reason codes. React renders them and does
  not infer access from role labels.
- Supported roles are `owner`, `admin`, `editor`, `uploader`, `analyst` and
  `viewer`; inactive membership grants no workspace access.
- `analyst` reads derived financial data but not raw import documents, mapping
  or review payloads; `viewer` is broader read-only access and may read them.
- Only owner/admin may read member and pending-invitation directories, including
  their email addresses.
- `Workspace.owner_id` and the single active owner membership must agree.
- Only the owner changes workspace identity and lifecycle. Ownership transfer
  is required before the owner can leave.
- Owner/admin member and invitation actions remain bounded by server policy;
  foreign workspace/member/invitation IDs receive privacy-safe outcomes.
- User-facing deletion is soft deactivate/restore. There is no hard-delete API.

Pure role and action policy lives in `permissions.py`. Request context and
membership guards live in `dependencies.py`.

Session navigation capabilities are `canReadWorkspace`,
`canWriteFinancialData`, `canManageImports`, `canViewRawImportData`,
`canViewMemberDirectory`, `canManageMembers`, `canViewWorkspaceActivity` and
`canManageWorkspace`. They are UI hints, not substitutes for API authorization.

## Application and transactions

`application/` owns the distinct workflows:

- `creation.py`: idempotent create plus committed session selection;
- `directory.py`: actor-scoped workspace directory;
- `switching.py`: expected-current check and committed session switch;
- `settings.py`: target-scoped read/update with optimistic concurrency;
- `members.py`: member directory, role and lifecycle transitions;
- `invitations.py`: one-time credential creation, preview, revoke and consume;
- `ownership.py`: locked ownership transfer and self-leave;
- `lifecycle.py`: locked deactivate/restore, fallback sessions and
  Chat/integration consequences.
- `activity.py`: manager-only safe projection and keyset-paginated
  administrative history.

Application services own commit/rollback boundaries. Repositories query and
flush only. Multi-row ownership, invitation and lifecycle transitions lock and
recheck authority inside one transaction.

Create operations use idempotency keys. Mutable snapshots use committed
timestamps or expected-current IDs. A boundary change returns a navigation
outcome; React performs hard navigation so cache, drafts and data from the old
workspace are not retained.

## Invitation identity and privacy

New invitations are bound to one normalized email and can be accepted only by
an active account with the same verified email. Removed membership is restored
in place; active and disabled membership require explicit handling. The current
identity email adapter sends the committed one-time link, while the create
response keeps the same transient share-link fallback.

Credentials are stored only as hashes and returned once after creation. Manager
list DTOs contain the invitee email but never credentials. Public preview exposes
only workspace name, role and expiry, with `Cache-Control: no-store` and
`Referrer-Policy: no-referrer`. Invalid, unbound, expired, revoked and replayed
tokens share a privacy-safe result. Accept remains CSRF-protected.

## Administrative activity

`GET /api/v1/workspaces/{workspaceId}/activity` is authorized against the target
membership before reading events. Owner/admin receive only allowlisted actor,
target and detail fields; credentials and arbitrary audit JSON never enter the
DTO. Ordering is `(created_at DESC, id DESC)`, with both values required for the
next-page cursor. React reloads the first page after a committed local workspace,
member or invitation mutation; no realtime infrastructure is involved.

## Tests

- `tests/api/test_workspaces_api.py`: JSON schemas, auth, masking,
  capabilities, idempotency and conflicts.
- `tests/api/test_workspace_activity_api.py`: activity schema, cursor and
  privacy-safe failures.
- `tests/features/workspaces/`: policies, isolation, application workflows and
  PostgreSQL concurrency/transaction invariants.
- `tests/features/workspaces/test_workspace_route_security.py`: retained public
  invitation privacy, CSRF and navigation.
- `frontend/app/features/workspaces/*.test.tsx` and `api/*.test.ts`: React state,
  forms, confirmations, focus and API adapters.
- `scripts/ui_audit.py`: current canonical/historical responsive browser audit.

Accepted product and migration policy is recorded in
`docs/architecture/decisions/0006-workspace-migration-policy.md`; the completed
migration summary is in `docs/frontend/plan/README.md`.
