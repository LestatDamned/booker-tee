# Workspaces vertical slices

Статус: D1–D14 accepted 2026-08-03; Slice 0 complete; Slice 1–4 production
gates passed.

## Ordering rationale

Workspace switch changes the authorization boundary for every migrated feature.
Therefore directory/switch authority must be proved before settings/member/
invitation UI. Public invitation routing is deliberately isolated because it
crosses authenticated/public presentation decisions.

## Slice 0 — characterization and policy lock

Outcome: no production behavior change.

- Record accepted D1–D14 in ADR-0006 (completed 2026-08-03, no deviations).
- Capture current SSR geometry at 1440/920/390 in isolated disposable data.
- Add PostgreSQL characterization for invitation accept/revoke race,
  last-owner race, current-session fallback and workspace delete blast radius.
- Use accepted single-owner policy and retain the public invitation SSR bridge.
- Specify deactivate impact on Chat/integrations and in-flight imports.

Gate: decisions accepted; no unresolved critical concurrency/isolation
ambiguity; exact existing behavior and intentional changes are named.

Progress 2026-08-03:

- completed: ADR-0006 policy lock;
- completed: authenticated legacy POST missing-CSRF matrix;
- completed: current session fallback/auto-create read-side-effect
  characterization;
- completed at audit time: deterministic service-level invitation replay and
  last-owner race reproduction as strict `xfail`; the last-owner cases became
  passing locked regressions in Slice 3;
- existing evidence retained: workspace hard-delete cascade characterization in
  `test_rule_delete_postgres.py`;
- completed: foreign workspace pre-lookup masking plus foreign/missing
  member/invitation service outcome characterization;
- completed: deterministic accept-vs-revoke race reproduction as strict
  `xfail`;
- completed: deactivate/restore persistence, session, Chat, integration and
  in-flight import impact contract in `API_AND_STATE.md`;
- completed: isolated minimal and rich owner-state browser geometry at
  1440/920/390; the rich mobile fixture proves a 254 px legacy overflow;
- completed at audit time: real PostgreSQL barriers proved two successful
  invitation accepts, successful accept plus revoke, and the former owner
  disable defect. Slice 3 replaced the owner case with passing locked legacy
  and authoritative transfer regressions; Slice 4 converted the invitation
  cases into ordinary passing locked regressions;
- completed: admin/editor/viewer browser capability and responsive geometry at
  1440/920/390, with nine pages free of overflow/browser errors;
- completed: expanded create/edit/invite, one-time credential and
  authenticated/public/expired/invalid invitation states across 24
  state/viewport combinations; exact focus/touch/announcement defects recorded;
- Slice 0 characterization complete; deactivate behavior remains an
  implementation-time replacement gate, not missing audit evidence.

## Slice 1 — directory, create and boundary switch

Presentation contract and standalone visual prototype accepted 2026-08-03:
[`SLICE_01_DESIGN_SPEC.md`](SLICE_01_DESIGN_SPEC.md),
[`prototype/index.html`](prototype/index.html). Production implementation and
replacement gate are complete.

```text
GET/POST /api/v1/workspaces
POST /api/v1/workspaces/:id/select
-> /app/workspaces
```

- Focused directory reader and creator/switcher application actors.
- Workspace-scoped/user-membership reads, API schemas/errors/CSRF.
- Create idempotency.
- Expected-current switch guard and committed session response.
- React directory, right-side create panel, responsive records and server
  capabilities.
- Full boundary navigation after switch; old drafts/data discarded.
- AppShell workspace link may become React-local only after slice gate.

Gate:

- foreign/inactive workspace cannot be selected or detected through response
  differences;
- switch changes all subsequent Accounts/Imports/Ledger/Reports/Rules reads;
- parallel old/new workspace responses cannot repopulate old UI;
- refresh/back/deep link and 1440/920/390 pass;
- legacy `/workspaces` remains operational; no redirect/delete yet.

Result 2026-08-03: all gates above passed. Real browser flow created and
selected a workspace, verified the committed session identity through Accounts,
Imports, Manual Ledger, Reports and Transaction Rules, restored the original
workspace, then passed 1440/920/390 geometry with zero console/page errors,
horizontal overflow or visible targets below 44 px
(`scripts/workspaces_slice01_browser.py`). AppShell and historical `/workspaces`
still point to legacy intentionally so settings/members/invitations are not
stranded before their replacement slices.

## Slice 2 — general settings and lifecycle read model

- Add `/app/workspaces/:workspaceId/settings` general section.
- Read/update name/type/default currency with `expectedUpdatedAt`.
- Show lifecycle impact facts/capabilities without implementing deactivate if
  D12 remains deferred.
- Keep route target workspace membership-scoped; current workspace ID is not
  assumed.
- On stale update, automatically replace the short form with authoritative
  values and ask the user to repeat the edit.

Gate: owner-only update, foreign/not-found masking, stale recovery, default
currency impact copy and personal/shared variants pass.

Implementation result 2026-08-03:

- added target-membership-scoped `GET/PUT /api/v1/workspaces/{id}` and
  `/app/workspaces/:workspaceId/settings`;
- update locks the target workspace, rechecks authoritative owner authority and
  `expectedUpdatedAt`, and commits workspace plus audit event atomically;
- settings DTO exposes identity, membership, server capabilities, supported
  type/currency options and owner-only lifecycle counts; it does not expose
  member/invitation identities or lifecycle mutation controls;
- React automatically replaces the three-field form with the authoritative
  server version on stale conflict, projects non-owner settings read-only and
  updates current AppShell identity after a successful save;
- focused API/application/React tests and real PostgreSQL lock/masking tests
  pass;
- production browser gate passes personal/shared settings, stale snapshot
  recovery and 1440/920/390 geometry. Full regressions pass with 773 backend
  tests plus 6 known strict xfails and 459 frontend tests. Exact evidence is in
  `TEST_MANIFEST.md`.

## Slice 3 — members and ownership

- Bounded member read API and server action capabilities/reasons.
- One inline member editor; role update, disable/reactivate.
- Implement leave and ownership transfer only if D8/D9 accepted in scope.
- Row locks/constraints protect last owner and owner/membership consistency.
- Session and Chat binding invalidation after removal/leave.

Gate: full role matrix, self/owner/admin boundaries, foreign IDs, concurrent
owner transitions, dirty edit/focus/dialog and mobile record geometry pass.

Implementation increments 2026-08-03:

- implemented bounded workspace-scoped member read plus role,
  disable/reactivate endpoints in `src/app/api/v1/workspaces/router.py` and
  `application/members.py`;
- workspace and member rows are locked before mutation; `expectedUpdatedAt`
  rejects stale writes and every target lookup includes workspace ID;
- disabling a member moves that user's active sessions away from the workspace,
  deactivates their Chat identity bindings and consumes their pending
  workspace/user conversation state in the same application transaction;
- `/app/workspaces/:workspaceId/settings` now renders the member collection
  inside the existing Workbench composition. API capabilities control inline
  role options and actions; disable uses the shared confirmation dialog;
- atomic transfer now locks workspace, session and all memberships, changes
  `Workspace.owner_id`, demotes the former owner to admin and promotes exactly
  one active recipient; a real PostgreSQL race gives one winner and preserves
  exactly one authoritative owner;
- non-owner self-leave requires an explicit confirmation, marks membership
  removed, revokes workspace Chat state and moves affected sessions to a
  deterministic active fallback. With no fallback the server returns
  `workspace_fallback_required` instead of silently creating a workspace;
- React uses server `canTransferOwnership`/`canLeave` capabilities, equal action
  geometry, shared confirmation dialogs and a hard boundary reload after both
  authority changes;
- legacy member mutations now acquire the same workspace/member lock order and
  cannot disable an owner; no legacy route/template was removed;
- application/API/React, PostgreSQL concurrency and production browser flows
  pass. `scripts/workspaces_slice03_browser.py` verifies a real invitee,
  member action geometry and transfer→leave at 1440/920/390/mobile-landscape
  with no overflow, undersized visible targets or browser errors;
- complete regressions pass with 789 backend tests plus 4 invitation-only
  strict `xfail`, 467 frontend tests and a production build;
- the extended production browser gate passes keyboard-only dialog/transfer/
  leave flow, focus return, 200% text scaling, reduced motion, stale member
  recovery, forbidden direct mutations and the complete owner/admin/editor/
  viewer projection at 1440/920/390/mobile-landscape. It also found and fixed
  the root `rem`-scaled minimum viewport and clipped mobile member actions;
- Slice 3 replacement gate is complete on 2026-08-04. Manual screen-reader
  testing is explicitly outside the accepted gate; semantic labels remain
  covered by component/browser assertions. Legacy member markup is still kept
  because it shares the invitation runtime required by Slice 4.

## Slice 4 — invitation administration

- Pending invitation metadata API.
- Idempotent create returning one transient share credential.
- Locked revoke and conflict recovery.
- No token in subsequent reads/activity/log DTOs.
- Keep current public preview/accept adapter until Slice 5 decision/gate.

Gate: role authority, cross-workspace masking, expiry/revoke/accept race,
one-time credential handling, no-store behavior and accessibility pass.

Implementation result 2026-08-04:

- `WorkspaceInvitationService` owns bounded read, idempotent create and locked
  revoke; owner/admin assignable roles and per-row revoke capability are
  server-projected, and admin cannot manage an admin invitation;
- deterministic `uuid5` plus stdlib HMAC provides safe retry without plaintext
  token persistence or a schema change. Only create/replay returns `shareUrl`;
  later reads contain metadata only and every invitation response is no-store;
- React settings uses one compact role form, transient copy panel, bounded
  responsive records, shared confirmation dialog and authoritative reload on
  `404/409`; no generic CRUD or new dependency was introduced;
- public preview remains SSR but is side-effect free, `no-store` and
  `Referrer-Policy: no-referrer`; public accept and legacy revoke now lock the
  invitation row, so accept/accept and accept/revoke PostgreSQL races have one
  winner;
- production browser gate passes owner/admin/viewer authority, token privacy
  after reload/list, public headers, stale revoke recovery, keyboard dialog
  flow and 1440/920/390/mobile-landscape geometry. Slice 4 replacement gate is
  complete; no legacy runtime was deleted because public accept is Slice 5.

## Slice 5 — public/authenticated invitation accept

Choose after D11:

- Option A (recommended first): retain a minimal hardened SSR bridge and move
  only its application/API authority to the new invitation service.
- Option B: add an explicit public React/auth route and production SPA/static
  routing outside `/app`.

Both options require login/signup return, expired/revoked/replayed privacy-safe
outcomes, CSRF on accept, atomic membership/session switch and safe navigation.

Gate: anonymous/authenticated/new-user/existing/disabled-member/concurrent
accept flows and token privacy pass. Only then may old invitation template/router
code be deleted or reduced.

## Slice 6 — deactivate/restore and cross-feature consequence

Only if D7/D12 accepted in this child stage:

- Locked deactivate/restore application use cases.
- Revoke pending invites; disable integrations/Chat bindings; invalidate pending
  conversation states; move sessions to deterministic fallback.
- Preserve all accounts/import documents/raw rows/rules/ledger/report history.
- Prevent in-flight stale context from committing after deactivation using a
  transactionally enforced guard appropriate to each mutation boundary.

Gate: cross-feature server tests plus browser/session/Chat flows prove immediate
loss of access, no data loss, safe restore and no old workspace drafts/cache.

## Slice 7 — canonical cutover and cleanup

- Switch AppShell/profile/dashboard/legacy shell links to canonical React route.
- Add query-preserving historical `GET /workspaces` redirect.
- Prove no legacy POST mutation surface remains.
- Execute [DELETE_MANIFEST.md](DELETE_MANIFEST.md), keeping named public/auth and
  non-browser consumers.
- Regenerate OpenAPI/types and remove legacy HTML operations.
- Run full replacement manifest and browser/theme audit.
- Collapse this temporary audit into durable feature contracts and Stage 7
  completion record; remove migration journal per documentation policy.

Gate: React/API is the only authenticated Workspaces presentation; every kept
legacy artifact has a named public/auth consumer; no runtime code was deleted
before its replacement evidence passed.

## Cross-slice rules

1. Each slice follows application/API -> runtime validation/state -> UI -> tests.
2. No HTML route is called from JSON API and no Jinja ViewModel is serialized.
3. No role/ownership/lifecycle decision is inferred in React.
4. No generic CRUD/form/table abstraction is introduced for visual symmetry.
5. Legacy remains working until the corresponding replacement gate.
6. Canonical navigation changes only after behavior, security and browser gates.
