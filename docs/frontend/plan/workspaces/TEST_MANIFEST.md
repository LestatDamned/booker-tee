# Workspaces replacement test manifest

Статус: proposed manifest; audit did not add or change tests.

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

Current gaps: no Workspaces route integration matrix, no versioned API, no
foreign-ID masking tests, no concurrent PostgreSQL invite/owner tests, no React
state/interaction tests and no dedicated workspace browser scenario.

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
- create/settings/member drafts survive 422 and 409;
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
13. keyboard-only navigation, Escape, focus return, screen-reader names;
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

