# Workspaces future delete/keep manifest

Статус: accepted gate manifest. Nothing listed here may be deleted before its
explicit replacement gate.

Slice 1–3 implementation result 2026-08-03: **nothing deleted**. Legacy `/workspaces`, its POST
handlers, presenters, templates, CSS, AppShell links and public invitation
bridge are deliberately retained because settings/members/invitations have not
all passed their replacement gates. Slice 3 browser/full-regression gates are
also pending. The new React directory/settings routes and
API coexist with them; settings links inside the React directory are canonical,
while cross-runtime entry links remain legacy until the authenticated workflow
cutover gate.

## Delete after full authenticated replacement gate

- `src/app/features/workspaces/router.py` authenticated directory and mutation
  routes. If public invitation bridge is retained, split it first into a named
  minimal adapter; do not delete it accidentally.
- `src/app/features/workspaces/presentation/models.py`.
- `src/app/features/workspaces/presentation/presenter.py`.
- `src/app/templates/workspaces/index.html`.
- `src/app/templates/workspaces/_workspace_card.html`.
- Replacement-only presenter/template/SSR tests in
  `tests/features/workspaces/test_workspace_ui_permissions.py` and any new
  characterization assertions explicitly superseded by API/React evidence.

## Conditional public invitation cleanup

Keep initially per D11:

- `GET/POST /workspaces/invitations/{invitation_token}...` adapter;
- `templates/workspaces/accept_invitation.html`;
- login/signup safe return integration.

Delete them only if a public React/auth route passes anonymous, authenticated,
login/signup return, CSRF, privacy and replay replacement gates. If retained,
the adapter must call the new invitation application actor and must not keep the
old all-purpose WorkspaceService merely for presentation compatibility.

## Remove or rewrite precisely after gate

- Workspaces router import/include from `src/app/main.py`; retain a public
  invitation router import if still active.
- Legacy workspace HTML/form operations from generated OpenAPI through normal
  regeneration, never hand-edit `frontend/app/api/generated/schema.ts`.
- Workspaces page entries/preparation/assertions in `scripts/ui_audit.py`;
  replace with canonical `/app/workspaces`, historical redirect and realistic
  React interactions.
- Workspace-only selectors in `src/app/static/css/app.css`:
  `.workspace-section*`, `.workspace-create*`, `.workspace-card*`,
  `.workspace-form*`, `.workspace-member*`, `.workspace-invitation*`,
  `.workspace-audit*` and their terms in responsive selector groups.
- `.invitation-share-*`, `.copy-row`, `.copy-input` only after confirming no
  public invitation or other named legacy consumer.
- Workspace-specific assumptions in generic legacy `_action.html` only when no
  other legacy consumer needs them; do not delete shared action/template code
  by selector name alone.
- `entity-target.js` only at the final legacy consumer gate; Workspaces itself
  does not justify retaining it after cutover.

## Modify, not delete

- `frontend/app/routes.ts`: register Workspaces routes.
- `frontend/app/shell/app-shell.tsx`: make workspace/profile transitions
  canonical at their respective replacement gates.
- `src/app/api/v1/router.py`: include Workspaces API router.
- `src/app/legacy_frontend_redirects.py`: add query-preserving
  `GET /workspaces -> /app/workspaces` only after SSR GET replacement.
- `tests/core/test_legacy_frontend_redirects.py`: add GET preservation and prove
  legacy POST methods are not redirected.
- `templates/base.html`, `templates/users/index.html`, dashboard onboarding and
  public home links: point to `/app/workspaces` after gate while these SSR
  consumers remain.
- `/api/v1/session` schema/mapper/frontend runtime schema if switch/session
  revision or navigation outcome is added.
- Stage 7 index: add a compact completion record only after all cleanup.

## Must preserve/evolve

### Domain/persistence

- `features/workspaces/models.py`, domain enums, migrations, FKs/indexes and
  audit provenance.
- Workspace ownership relationships from Accounts, Imports, Ledger, Categories,
  Properties and Transaction Rules.
- `permissions.py` or its explicitly evolved server capability policy.
- token hashing/generation, hardened behind the invitation actor.

### Application/repository

- Workspace/session/signup/login behaviors used by `AuthenticationService`.
- `WorkspaceContext` and all financial API/application consumers.
- Workspace-scoped repository queries; split by aggregate if cohesion requires,
  but do not create a generic repository façade.
- Chat resolver/switcher/identity binding and its tests.
- Transaction Rules/import/ledger consumers and workspace locks.
- Domain/application tests that prove security/financial invariants rather than
  legacy rendering.

### Remaining presentation

- Legacy `base.html`, global CSS, Alpine/HTMX and public/auth templates while
  Dashboard/Profile/other named Wave C consumers remain.
- React UI Foundation components and semantic CSS; Workspaces composes them and
  does not copy their internals.

## Exact current consumer references to explain at cleanup

- `src/app/main.py` Workspaces router registration.
- `frontend/app/shell/app-shell.tsx` two workspace links.
- `src/app/templates/base.html` context/nav links.
- `src/app/templates/users/index.html` profile link.
- `src/app/templates/components/onboarding_checklist.html` workspace step.
- `src/app/templates/home.html` setup link.
- `src/app/features/users/router.py` default safe next path.
- `src/app/features/users/service.py` membership/session selection.
- `src/app/features/chat_integrations/use_cases/workspace.py` and identity use
  cases.
- all imports of `WorkspaceContext`, `WorkspaceRepository`, workspace models and
  permission dependencies in financial features.

## Delete gate searches

```bash
rg -n "WorkspacesPagePresenter|WorkspacesPageVM|workspaces/(index|_workspace_card)\.html" src tests frontend scripts
rg -n "workspace-(section|create|card|form|member|invitation|audit)|invitation-share" src tests frontend scripts
rg -n '"/workspaces"|/workspaces/|/workspaces\?' src tests frontend scripts
rg -n "WorkspaceContext|WorkspaceRepository|WorkspaceService|WorkspaceMember|WorkspaceInvitation" src tests frontend
```

Allowed after cleanup must be classified as one of:

- canonical `/app/workspaces*` or `/api/v1/workspaces*`;
- historical GET redirect/test;
- retained public invitation bridge;
- auth/session/Chat/domain/persistence consumer;
- explicit test fixture or migration.

Any legacy authenticated POST route, Jinja index/card/presenter, workspace-only
global selector or unexplained generated HTML operation fails the gate.
