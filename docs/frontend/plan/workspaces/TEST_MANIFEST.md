# Workspaces replacement test manifest

Статус: accepted replacement manifest; Slice 0 characterization and Slice 1–2
production gates complete.

## Existing evidence

| Area | Existing tests | What they prove |
| --- | --- | --- |
| Permission matrix | `tests/features/workspaces/test_workspace_permissions.py` | role capability functions and disabled membership |
| Invitations | `test_workspace_invitations.py` | token hash, one returned credential, basic accept, expiry mutation |
| Members | `test_workspace_member_management.py` | self-role, admin escalation, sequential last-owner, owner disable |
| Legacy UI | `test_workspace_ui_permissions.py` | one base-header viewer assertion |
| Signup/session helpers | `tests/features/users/test_users_workspaces.py` | atomic signup, local return path, CSRF primitives |
| Session API | `tests/api/test_session_api.py` | session DTO/capabilities, API error/CSRF infrastructure |
| Chat | `tests/features/chat_integrations/test_identity_workspace.py`, `test_service_dashboard.py` | active binding resolution and switch orchestration |
| Existing UI audit script | `scripts/ui_audit.py` | workspace page is visited; realistic scenario asserts pending invitation only |

## Slice 0 evidence added after policy acceptance

| Evidence | Test | Result on 2026-08-03 |
| --- | --- | --- |
| Every authenticated legacy workspace POST rejects a missing form CSRF token before session/service work | `test_workspace_route_security.py` | 9 route cases pass |
| Current invalid-current fallback commits during context resolution | `test_workspace_context_characterization.py` | characterization passes |
| Current no-membership read silently creates a personal workspace and audit event | `test_workspace_context_characterization.py` | characterization passes |
| Two concurrent users can pass the invitation status guard and consume one credential | `test_workspace_invitation_concurrency.py`, `test_workspace_concurrency_postgres.py` | service and real PostgreSQL strict `xfail`; PostgreSQL proves 2 commits and 2 memberships |
| Accept and revoke can both pass independent pending snapshots | `test_workspace_invitation_concurrency.py`, `test_workspace_concurrency_postgres.py` | service and real PostgreSQL strict `xfail`; PostgreSQL proves both commit |
| Two owners could concurrently pass the legacy count guard and disable each other | `test_workspace_owner_concurrency.py`, `test_workspace_concurrency_postgres.py`, `test_workspace_ownership_postgres.py` | **Resolved Slice 3:** owner disable is rejected; transfer uses locked single-owner transition and its PostgreSQL race has one winner |
| Non-current workspace is rejected before member/invitation route lookup | `test_workspace_route_security.py` | 5 route cases pass with identical 404 |
| Foreign and missing member/invitation IDs use the same scoped service outcome | `test_workspace_isolation_characterization.py` | 4 outcomes pass; current workspace ID asserted |
| Minimal owner SSR geometry at 1440/920/390 | `scripts/ui_audit.py --authenticated --scenario empty --path workspaces` | 3 pages pass; zero overflow/errors |
| Rich owner SSR geometry with multiple workspaces/member/pending invite/long labels | isolated `scripts/ui_audit.py --authenticated --path workspaces` fixture | desktop/tablet pass; mobile fails with 254 px overflow from member/title/meta widths; zero browser errors |
| Admin/editor/viewer SSR capability geometry | isolated shared-role fixture + `scripts/ui_audit.py --authenticated --path workspaces` | 9 pages pass at 1440/920/390; actions match server policies; zero overflow/errors |
| Expanded create/edit/invite, one-time credential and valid/expired/invalid preview geometry | isolated Playwright interaction capture, `/tmp/booker-workspaces-forms-20260803/report.json` | 24 state/viewport combinations pass overflow/error gate; focus, labels and touch sizes measured |

The remaining strict `xfail` cases concern invitation consume/revoke and must be
converted to ordinary passing tests in Slice 4–5. The former owner-disable
characterizations are now ordinary passing regression tests, supplemented by a
real concurrent transfer test. Database tests use ordinary flush/commit and
real PostgreSQL locking: no fake transaction implementation is involved.

Current gaps after Slice 2: PostgreSQL invitation/last-owner locking fixes
remain later-slice work but their failure mode is no longer ambiguous. Settings
now has application/API/React evidence plus a real database-backed
foreign/missing and concurrent-stale matrix. Members, invitations and lifecycle
mutations still have no replacement evidence.

The accepted Slice 1 contract now has a standalone non-runtime visual prototype
at `docs/frontend/plan/workspaces/prototype/index.html`. Its 2026-08-03 capture
produced 24 Mocha/Latte state/viewport combinations with zero horizontal
overflow, sub-44 px visible targets, console errors or page errors. This is a
visual/preflight artifact, not React/API replacement evidence; the browser gates
below remain mandatory for production.

## Slice 1 production evidence

| Evidence | Test/command | Result on 2026-08-03 |
| --- | --- | --- |
| Directory ordering, capabilities and inactive projection | `test_workspace_directory_application.py` | pass |
| Create atomicity/idempotency and session switch | `test_workspace_slice01_mutations.py`, `test_workspaces_api.py` | pass |
| Real PostgreSQL concurrent switch/create | `test_workspace_slice01_postgres.py` | 2 pass; exactly one stale-switch winner and one create aggregate |
| React DTO, create/switch recovery and accessible UI | `workspaces-api.test.ts`, `workspaces-page.test.tsx`, `routes/workspaces.test.tsx` | 15 pass; shared panel focus test also passes |
| Cross-feature hard boundary and responsive browser flow | `scripts/workspaces_slice01_browser.py` | Accounts/Imports/Ledger/Reports/Rules identity verified; 1440/920/390 pass, zero browser errors/overflow/sub-44 px targets |
| Full backend regression on clean Alembic head | `pytest -q` with isolated PostgreSQL | 761 pass, 6 known strict xfail |
| Full frontend regression in bounded Vitest groups | all 73 `*.test.*` files | 446 pass |

The first full backend attempt against `booker_tee_reparse_test` exposed schema
drift: its `alembic_version` was obsolete `20260727_0020` and the transaction
rule provenance FK still used `SET NULL`. A new isolated database migrated from
empty to current `20260802_0021` produced the clean result above. This was a
test-environment failure, not a Workspaces code regression. The disposable
`booker_tee_reparse_test` database was then recreated at current head; the two
Slice 1 PostgreSQL concurrency cases and the previously failing FK guard pass
there (`3 passed`). The temporary verification database was removed.

## Slice 2 production evidence

| Evidence | Test/command | Result on 2026-08-03 |
| --- | --- | --- |
| Target-scoped read, owner-only update, normalization, lifecycle privacy and rollback | `test_workspace_settings_application.py` | pass |
| Auth/CSRF, response schema, 403/404 masking, 409 stale and 422 fields | `test_workspaces_api.py` | pass |
| Real row lock gives exactly one winner; foreign/missing outcomes match | `test_workspace_settings_postgres.py` | 2 pass |
| Strict runtime DTO parsing and stable errors | `workspace-settings-api.test.ts` | pass |
| Owner form, read-only member projection, stale snapshot reset and lifecycle copy | `workspace-settings-page.test.tsx` | pass |
| Deep-link loader/route states and directory settings links | `routes/workspace-settings.test.tsx`, existing Workspaces React tests | pass |
| Personal/shared owner flow, current shell identity, real stale snapshot recovery and 1440/920/390 geometry | `scripts/workspaces_slice02_browser.py` | pass; one expected 409, zero unexpected console/page errors, overflow or visible targets below 44 px |
| Full backend regression on current PostgreSQL head | `pytest -q` with `BOOKER_TEE_TEST_DATABASE_URL` | 773 pass, 6 known strict xfail |
| Full frontend regression | `vitest run` | 76 files, 459 pass |

Screenshots and the machine-readable browser report are disposable artifacts in
`/tmp/booker-workspaces-slice02-browser`; they are not runtime assets.

## Server/application tests required

### Directory/session

- list only memberships of actor; active/inactive policy and stable ordering;
- no foreign workspace facts/counts/capabilities;
- no commits or silent workspace creation during directory read;
- current session workspace always belongs to active membership;
- deterministic no-workspace/fallback outcome;
- switch validates target membership and active workspace under session lock;
- `expectedCurrentWorkspaceId` catches stale tab;
- repeat switch returns same truthful session result.

### Create/settings

- create workspace + owner membership + audit in one transaction;
- Idempotency-Key replay and changed-payload conflict;
- rollback leaves no partial workspace/membership/audit;
- owner-only settings, foreign/not-found same result;
- validation fields and normalization;
- stale `updatedAt` conflict; committed timestamps returned;
- default currency update does not rewrite financial history.

### Members/ownership

- complete role/capability matrix, including admin-to-admin/owner denial;
- every member lookup filters `(workspace_id, member_id)`;
- foreign and absent member indistinguishable;
- self-role/self-disable/remove guards;
- leave policy and current-session fallback;
- ownership transfer atomically updates `owner_id` and memberships;
- concurrent transfer/disable cannot leave zero/multiple authoritative owners;
- disabled/removed member loses web and Chat access immediately.

Current Slice 3 increment evidence:

- `tests/features/workspaces/test_workspace_members_application.py` covers
  foreign masking, server capability projection, stale-before-side-effect and
  session/Chat invalidation orchestration;
- `tests/api/test_workspaces_api.py` covers camelCase member DTOs, expected
  timestamps, stable conflict/reason-code envelopes and masked member IDs;
- `frontend/app/features/workspaces/workspace-settings-page.test.tsx` covers
  server-driven inline role changes, disable, ownership-transfer and self-leave
  confirmations plus hard-boundary navigation;
- `tests/features/workspaces/test_workspace_ownership_application.py` covers
  atomic role/owner changes, stale rejection, owner-leave blocking, session
  fallback and Chat revocation;
- `tests/features/workspaces/test_workspace_ownership_postgres.py` proves two
  concurrent transfers have exactly one winner, one audit event and one active
  owner matching `Workspace.owner_id`;
- `workspace-members-api.test.ts` and `test_workspaces_api.py` cover CSRF,
  workspace/member/session timestamps, response navigation and fallback
  session projection;
- `scripts/workspaces_slice03_browser.py` creates real admin/editor/viewer
  memberships via the retained invitation bridge; verifies server-projected
  role actions and forbidden direct mutations; captures
  1440/920/390/mobile-landscape plus desktop/mobile at 200% text; verifies no
  overflow, clipped actions, sub-44 px visible targets or browser errors; tests
  reduced motion and stale conflict recovery; and completes keyboard-only
  ownership transfer followed by former-owner leave and fallback reload;
- full regressions: 789 backend passed with 4 invitation-only strict `xfail`;
  77 frontend files/467 tests passed; OpenAPI check, format, lint, typecheck,
  style policy and production build passed;
- the extended gate passed on 2026-08-04. Manual screen-reader testing was
  removed from the accepted Slice 3 gate by product decision; accessible names
  and dialog semantics continue to have automated assertions.

### Invitations

- create authority, invitable roles and workspace binding;
- hash-only persistence and transient credential response;
- idempotent create replay;
- list never exposes token/hash;
- preview is side-effect free and no-store;
- accept/revoke compare-and-consume under lock;
- concurrent accept by two users yields exactly one accepted membership;
- accept vs revoke race has exactly one winner;
- invalid/expired/revoked/replayed public shape does not leak credential state;
- disabled existing membership cannot be reactivated by invite;
- accept switches session only after membership commit.

### Lifecycle

- deactivate/restore owner authority and stale token;
- no hard-delete application path;
- pending invites revoked, integrations/bindings disabled, conversation states
  invalidated in same transaction or explicitly consistent transaction set;
- all web sessions receive valid fallback/no-workspace outcome;
- Accounts, documents/raw rows, rules, operations/money entries, categories and
  properties remain persisted and unchanged;
- inactive workspace blocks every API/Chat read/write;
- concurrent in-flight write cannot commit after lifecycle guard.

## API contract tests required

For every endpoint:

- `401` unauthenticated JSON, never login redirect;
- `403` capability failure only where allowed by privacy contract;
- `404` absent/foreign masking;
- `409` stale/idempotency/transition conflicts with stable code;
- `422` field errors/blocking reason codes;
- safe `5xx` envelope without private data;
- CSRF header required for all unsafe methods;
- URL/body workspace ID never overrides authenticated authority;
- response validates Pydantic/OpenAPI schema and contains no ORM/private fields;
- read endpoints have no persistence side effects.

OpenAPI/type generation tests must prove legacy HTML operations disappear only
after cutover and new schemas are camelCase/generated/runtime-validated.

## React adapter and state tests required

- runtime schema accepts valid DTO and rejects malformed identity/capabilities;
- URL parser normalizes supported filter/section values and preserves Back/
  Forward state;
- loader handles loading, 401, 403/404, network and malformed response;
- switch success discards old snapshots/drafts and performs safe boundary
  navigation; late old-workspace response is ignored/aborted;
- switch conflict refreshes session truth;
- create/member drafts survive recoverable errors; settings retains input on
  `422` but resets its short form to the authoritative snapshot on `409`;
- pending buttons disable double submit and expose busy state;
- one-time invite credential disappears on dismissal/navigation and is absent
  after reload;
- server capabilities/reason codes control availability; role strings are not
  used as authority;
- dirty panel/editor requires explicit discard before switch/close;
- Toast/InlineNotice/RouteState behavior and retry path;
- focus first invalid field, focus return from panel/dialog and Escape behavior;
- current workspace uses `aria-current`; role/status are textual;
- desktop and mobile records maintain one logical reading/action order.

## Cross-feature regression manifest

After switch/deactivate/member removal, test at minimum:

- `/api/v1/session` identity and CSRF continuity;
- Accounts directory/detail and balances;
- Import documents/upload/detail/mapping/review;
- Manual Ledger list and drafts;
- Reports filters/aggregates;
- Categories/Properties/Transaction Rules references;
- Chat dashboard/manual/upload/review and workspace selector;
- legacy Dashboard/Profile while they remain SSR;
- login/signup invitation return path.

No financial aggregate may combine old/new workspace state. Draft entity IDs
from the old workspace must produce masked not-found after switch.

## Browser scenarios

Slice 1 uses the exact presentation states and interaction contract in
[`SLICE_01_DESIGN_SPEC.md`](SLICE_01_DESIGN_SPEC.md). Its focused matrix adds
normal, long-name, inactive, explicit no-workspace, switch/create pending,
stale-tab conflict and ambiguous-timeout recovery. Run it keyboard-only and at
200% text zoom in addition to the standard viewport/theme matrix; verify
reduced motion, visible focus, live announcements and that hidden responsive
projections never enter the tab order.

Run in Mocha and Latte at 1440x1000, 920x900 and 390x844:

1. deep-link/reload `/app/workspaces` and historical query redirect;
2. create (including double-click/retry), committed selection and Toast;
3. switch from A to B, verify shell plus Accounts/Imports/Ledger/Reports data;
4. Back/Forward cannot resurrect A data/drafts;
5. owner settings update and stale second-tab recovery;
6. admin/viewer read-only capability differences;
7. member role/disable/reactivate and confirmation/focus;
8. ownership transfer/leave if accepted;
9. invitation create/copy/revoke and privacy after reload;
10. anonymous login/signup accept, replay/expiry/revoke;
11. deactivate/fallback/restore if accepted;
12. long names/emails, empty/minimal and large member/workspace collections;
13. keyboard-only navigation, Escape, focus return and automated accessible
    names (manual screen-reader run is not required for Slice 3);
14. no horizontal overflow, console/page/request errors.

## Replacement mapping

| Legacy observation | Replacement evidence |
| --- | --- |
| `WorkspacesPagePresenter` action policy | application/API capabilities + React projection tests |
| SSR create/edit draft/error | React form + API 422/409 tests |
| POST switch + `next` redirect | session switch application/API + boundary browser flow |
| member/invite action forms | API authority/concurrency + React dialog/focus tests |
| one-time Alpine copy panel | transient React credential state + privacy tests |
| legacy card responsive CSS | `ResponsiveRecordCollection` tests + browser widths |
| `hx-confirm` | `ConfirmationDialog` interaction/browser tests |
| public invitation Jinja | retained bridge tests or public React replacement tests |
| workspace entry links | canonical link + historical redirect tests |

## Audit-stage commands

The audit itself may run existing focused tests, import/route introspection,
`rg` consumer searches and Markdown/link checks. It must not run the realistic
UI scenario against normal developer data because that script creates users,
workspaces, invitations and financial fixtures.
