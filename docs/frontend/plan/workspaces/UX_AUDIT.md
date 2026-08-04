# Workspaces UX/UI audit

Статус: factual static audit + complete isolated browser baseline + accepted
React composition. Rich permission/member/invitation states remain pending.

## Existing information architecture

`templates/workspaces/index.html` помещает в одну bordered `.panel` четыре
разные задачи в таком порядке:

```text
toolbar: user + “Настройки пространства” + profile link
summary: current workspace / role / user / workspace count
access:
  members
  create invitation + one-time link
  pending invitations
workspaces:
  create workspace
  current workspace
  other workspaces
activity log
```

Факты: access administration визуально предшествует основной directory/switch
задаче; page title говорит только о settings; direct deep links к sections нет.
Это хорошо для небольшого private setup, но хуже масштабируется при нескольких
workspace/members/events.

## Existing interaction audit

### What is already useful

- Current and available workspaces have explicit text status, not color only.
- Member role/status, invitation role/expiry and audit actor/target are textual.
- Actions have text labels and 44–48 px minimum heights in shared legacy CSS.
- Forms use visible labels and native controls.
- Current workspace is visible in both legacy and React shells.
- Mobile CSS collapses entity cards at 920 px and form grids at 560 px.
- One-time invitation copy explicitly says that the link is shown once and
  should be shared through a trusted channel.

### Problems to carry into replacement requirements

1. There is no route/local loading feedback or pending button state; double
   submit remains possible.
2. Most validation errors leave the prepared page and lose drafts. Only invite
   create rerenders in context.
3. Success after switch/settings/member mutation is silent and returns to page
   top; row focus and anchor are not restored.
4. Inline edit uses a visually hidden `<summary>` triggered through inline
   `onclick`. Focus/expanded state and dirty-close protection are not explicit.
5. Revoke/disable confirmation relies on unverified `hx-confirm`; no semantic
   dialog/focus-return contract is tested.
6. Empty workspace state conflicts with silent session auto-creation; users
   cannot understand a genuine no-access/recovery state.
7. Activity, members and directory are all eager-loaded. At larger sizes the
   page becomes a long collection without search/pagination or section deep
   links.
8. `truncate-label` uses one-line ellipsis for workspace/user identity. Full
   value exists in `title`, but touch/screen-reader recovery is weaker than safe
   wrapping where space permits.
9. Public invalid invitation returns a styled error with HTTP 200; semantics and
   recovery differ from API error conventions.
10. Switching is available only after navigating away from the current feature;
    there is no switch pending state or clear statement that old drafts/context
    will be discarded.

## Existing responsive geometry

Source: `static/css/app.css`, `base.html`, workspace templates.

- Global shell: `min(100% - 32px, 1120px)`; page vertical padding 32 px.
- Main legacy panel: 24 px padding, reduced to 16 px below 560 px.
- Entity card desktop: content + actions (`minmax(180px, auto)`), 14 px padding,
  16 px gap; becomes one column at 920 px.
- Create/settings forms use 12 columns: name 6, type 3, currency 3. Member role
  uses 6. All collapse to one column below 560 px.
- Header becomes a compact two-row mobile composition below 720 px. Navigation
  becomes a two-column expandable grid.
- Audit widths in project contract are 1440/920/390. Static rules cover those
  transitions.

## Isolated browser baseline — 2026-08-03

The legacy page was run against a dedicated temporary PostgreSQL database with
three disposable signup users and no copied application data:

```text
scripts/ui_audit.py --authenticated --scenario empty --path workspaces
theme: catppuccin-mocha
desktop: 1440x1000
tablet:  920x900
mobile:  390x844
```

The report passed all three viewports with HTTP 200, zero horizontal overflow,
no overflow offenders, console errors, page errors or failed requests. Images
and `report.json` were written to
`/tmp/booker-workspaces-baseline-20260803`; they are audit artifacts, not
committed product assets. The disposable database contained three users and
three personal workspaces and was dropped after capture.

Visual inspection confirmed:

- desktop keeps the 1120 px workbench and a compact single-row primary nav;
- tablet wraps primary navigation and expands record actions to full width;
- mobile collapses navigation, summary metrics, records and audit content to one
  logical column without clipping; long audit email wraps within its card;
- text status remains visible independently of color at every width.

Visual/semantic problems confirmed rather than inferred:

1. Native details summaries render the disclosure marker plus both literal
   strings “Открыть Закрыть”, producing ambiguous visible and announced labels.
2. Page title “Настройки пространства” does not describe its combined access,
   directory, switching and creation responsibilities.
3. Member email and role are concatenated as ordinary text instead of separate
   role/status primitives; long mobile identity is hard to scan.
4. Audit metadata uses terse `кто:`, entity and details fragments. On mobile it
   becomes a tall technical card rather than a readable activity sentence.
5. The edit workspace action becomes a visually loud full-width green button at
   tablet/mobile widths even though directory switching/identity should remain
   the page priority.
6. The “empty” scenario is actually the minimum reachable state: session signup
   always creates one personal workspace, owner membership and audit event. A
   true no-workspace recovery state still has no browser baseline.

The baseline does not prove focus order, disclosure announcements, destructive
confirmation, expanded create/edit forms, one-time credentials or non-owner
capabilities; those remain explicit scenarios below.

### Rich owner-state browser finding — 2026-08-03

A second isolated run used one owner, two workspaces, a pending invitation, a
second member and synthetic long Russian display/workspace names. The same
1440/920/390 viewport matrix was written to
`/tmp/booker-workspaces-rich-20260803`. Desktop and tablet passed without
horizontal overflow or browser errors. Mobile failed the geometry gate with
`horizontal_overflow_px: 254`; it had no console or page errors.

The report identifies the exact legacy offenders rather than inferring them:

- `.workspace-member-card__topline`, `.workspace-member-card__title` and its
  `.truncate-label` resolve to 596 px for the long member display name;
- `.workspace-member-card__meta` also resolves to 596 px for email plus role;
- the long workspace title resolves to 363 px and contributes a smaller
  overflow beyond the content column.

The screenshot also confirms that the long member title is visually clipped,
while its email and role remain concatenated. This is accepted only as a
characterized legacy defect. The React replacement must satisfy the explicit
390 px wrapping/no-page-overflow gate; this audit does not authorize a legacy
CSS fix.

### Server-role browser matrix — 2026-08-03

An isolated shared workspace with owner/admin/editor/viewer memberships was
audited at 1440/920/390. Reports and screenshots are in:

- `/tmp/booker-workspaces-role-admin-20260803`;
- `/tmp/booker-workspaces-role-editor-20260803`;
- `/tmp/booker-workspaces-role-viewer-20260803`.

All nine pages passed with HTTP 200, zero horizontal overflow, console/page
errors or failed requests. The database contained only synthetic identities,
memberships and sessions and was dropped after capture.

Visual inspection agrees with the server presenter/policies:

- admin sees invitation creation and role/disable actions for editor/viewer,
  but not for owner, self or the other admin; workspace edit is absent;
- editor and viewer see the complete member directory read-only, with no
  invitation, member-management or workspace-settings actions;
- workspace creation remains visible to every authenticated role because it
  creates a new actor-owned workspace rather than mutating the current shared
  workspace;
- AppShell primary action is capability-sensitive: editor retains upload,
  while viewer receives reports instead;
- role/status remain readable without color, but email and role are still one
  undifferentiated metadata string.

This proves current presentation behavior only. React/API capabilities still
must be returned by the server with stable reason codes; the client must not
reconstruct this matrix from role names.

### Geometry risks

- 920 px immediately collapses actions under every record, increasing vertical
  height for members/invitations/workspaces.
- The legacy full-width action column can create repeated loud buttons; current
  React `ActionStack orientation="row"` is a better proven compact contract.
- One-time invitation link/copy statically collapses from two columns, but long
  credential text still requires browser `overflow-wrap`/scroll testing at
  390 px.
- A long activity list and multiple member edit rows compete with directory
  priority on mobile.

## UI Foundation reuse matrix (proposed)

| Responsibility | Use | Workspace-specific composition |
| --- | --- | --- |
| Page geometry | `PageFrame`, `WorkbenchSurface`, `WorkbenchHeader`, `PageHeader` | Directory title, current context and one create CTA |
| Directory controls | `WorkbenchToolbar`, `WorkbenchSearch` only if measured lists justify it, `WorkbenchStatus` | Active/archived membership filters after D7/D12 |
| Records | `ResponsiveRecordCollection`, `WorkbenchRow` | Workspace identity/type/currency/role/current status and switch action |
| Create | `WorkbenchPanel` | Workspace name/type/currency draft; dirty close guard |
| Settings identity | `WorkbenchPanel` only for page-level identity or dedicated settings section | Do not force collection inline edit onto settings semantics |
| Member edit | `ExpansionPanel` under member row | Native fixed-role `<select>`; `SearchableSelect` is not justified for six roles |
| Invite create | `WorkbenchPanel` or local settings section after D3 | Native role select; one-time credential share panel remains feature-local |
| Actions | `Button`, `RouterButtonLink`, `ActionStack` | Switch as primary safe action; lifecycle/admin actions in overflow/danger group |
| Status | `StatusLabel`, `Badge`, `Tag` | Status=StatusLabel, member/workspace counts=Badge, role/type=Tag |
| Forms | `Field`, `Fieldset`, `FormGrid`, `FormActions`, `FormErrorSummary` | Server field errors and preserved draft |
| Destructive | `ConfirmationDialog` | Revoke/remove/leave/transfer/deactivate copy and impact facts |
| Feedback | `RouteLoadingPage`, `RequestState`, `InlineNotice`, Toast | Boundary switch pending, stale recovery, committed success |

`SearchableSelect` is appropriate only if a future member picker searches a
large user directory. It is not appropriate for workspace type, currency or
role fixed option sets.

## Proposed directory geometry

```text
AppShell
└─ PageFrame
   └─ WorkbenchSurface
      ├─ WorkbenchHeader / PageHeader
      │  ├─ “Пространства”
      │  ├─ current workspace + role context
      │  └─ “Создать пространство”
      ├─ WorkbenchToolbar (only proven filters/search)
      ├─ WorkbenchStatus
      └─ ResponsiveRecordCollection
         ├─ desktop rows: identity | type/currency | role/status | action
         └─ mobile records: identity/status -> facts -> primary/overflow

create -> right-side WorkbenchPanel
settings -> /app/workspaces/:workspaceId/settings
switch -> boundary mutation -> safe hard navigation/reload
```

The directory should not become a universal tenant CRUD table. Its record
semantics are “where the entire financial application is currently scoped”,
not merely an editable entity.

## Proposed settings geometry

- General identity and lifecycle are page-level sections.
- Members use responsive records; edit one member inline at a time.
- Invitations show bounded pending credentials without ever returning token
  values. Create returns one transient share credential kept only in local
  component state until dismissed/navigation.
- Activity is bounded/lazy and secondary. It must not expose token hashes,
  secrets or unlimited details JSON.
- Personal/shared use the same shell; unavailable collaboration section shows
  a server reason only when the user may know the feature exists.

### Slice 1–2 visual hardening — 2026-08-03

- Directory uses the same header/table/action rhythm as Accounts and
  Properties: one count eyebrow, one clear title, no duplicate current-workspace
  status strip and a stable two-column action grid.
- Programmatic route focus keeps its screen-reader announcement without drawing
  a non-interactive rectangle around the page title.
- Settings uses one `WorkbenchSurface` with flat, divider-separated sections;
  nested card-on-card presentation was removed.
- User-facing copy avoids internal terms such as `workspace`, `Read-only`,
  `lifecycle` and `Chat binding`; mobile form actions use short labels that do
  not wrap.
- Production captures at 1440/920/390 pass without horizontal overflow,
  undersized visible targets, console errors or page errors
  (`scripts/workspaces_slice01_browser.py`,
  `scripts/workspaces_slice02_browser.py`).

## Accessibility and keyboard contract (proposed gate)

- Route change focuses main heading; AppShell skip link continues to work.
- Desktop and mobile record order use one semantic data order; no duplicated
  interactive DOM with ambiguous tab stops.
- Switch, create, settings and overflow are reachable by keyboard with visible
  focus and 44 px hit areas.
- Dialog initial focus: cancel for destructive, first meaningful field for
  create; close restores trigger.
- Dirty panel/member edit blocks accidental dismissal and explains the choice.
- Role/status/current state are announced as text; `aria-current` marks current
  workspace.
- Pending mutation sets disabled/busy on the initiating button and prevents
  duplicate submit.
- Error summary focuses first invalid field. For short workspace settings a
  `409` automatically reloads authoritative values and asks the user to repeat
  the edit; longer workflows may offer reload/retry/discard with draft
  preservation.
- Toast uses polite live status and never steals focus.
- At 390 px no horizontal page overflow; long workspace names, emails and invite
  links wrap or use an explicitly accessible disclosure.
- Reduced motion applies to row highlight/panel transitions.

### Slice 3 accessibility/responsive closure — 2026-08-04

- Production browser coverage confirms keyboard-only ownership transfer and
  leave, destructive-dialog initial focus, Escape and trigger focus return.
- Owner/admin/editor/viewer render only server-authorized role and lifecycle
  actions; direct unauthorized mutations are rejected independently of UI.
- 200% text scaling passes at 1440 and 390 CSS px without page overflow or
  clipped member actions. The audit replaced the root `20rem` minimum width,
  which scaled to 640 px, with a 320 px viewport floor and stacks member
  actions across the full mobile record width.
- Reduced-motion preference is active in the browser scenario; standard
  1440/920/390/mobile-landscape captures retain at least 44 px visible targets.
- A manual screen-reader run is intentionally not part of the accepted Slice 3
  gate (product decision 2026-08-04). Existing semantic labels, roles and
  accessible-name assertions remain in place; no accessibility behavior was
  removed from runtime.

## Browser baseline closure before implementation

Before changing presentation, capture current SSR at 1440/920/390 for:

1. owner with multiple workspaces, members, pending invites and activity;
2. admin/member/viewer permissions;
3. create/edit expanded states;
4. one-time invitation link;
5. invalid/expired invitation preview;
6. true no-workspace recovery state.

### Form, credential and invitation-state capture — 2026-08-03

Items 3–5 were captured in an isolated database across 1440/920/390. Eight
states per viewport (24 total) cover expanded create, expanded edit, expanded
invite, one-time credential, authenticated valid preview, public valid preview,
expired preview and invalid preview. Screenshots and the measurement report are
in `/tmp/booker-workspaces-forms-20260803`.

All 24 combinations have zero horizontal overflow, console/page errors or
failed requests. Browser measurements and visual inspection establish:

- create, edit and invite native `<details>` open through Enter and retain
  focus on their summary; the native element carries the state, while no
  explicit `aria-expanded` attribute is rendered;
- visible name/type/currency/role controls have associated labels; hidden CSRF
  input correctly has none;
- form inputs/selects are 40 px high and the broad disclosure summaries are
  42 px on desktop/tablet, below the accepted 44 px target gate;
- the opened workspace edit drawer intercepts pointer events over its own
  summary, so a pointer click cannot close it; keyboard Enter still closes it;
- the one-time link is readonly and has `aria-label="Ссылка приглашения"`, the
  disclosure remains open and mobile has no page overflow;
- after the invitation POST/full reload, focus is `body`; the share panel has
  neither `aria-live` nor a status role, so the new credential is not
  proactively announced;
- authenticated valid preview renders one accept form; public valid preview
  renders login/signup recovery and only workspace display name, role and
  expiry;
- expired and invalid previews expose no workspace metric. Expired uses the
  specific message “Срок действия приглашения истек.”, while an unknown token
  uses the generic invalid message.

The minimal owner state and items 1–5 are now captured at all three widths.
Long names/emails expose the separate 254 px mobile overflow documented above.
The true no-workspace state cannot be reached through current runtime because
context resolution silently creates a personal workspace; that behavior is
already proved by `test_workspace_context_characterization.py` and is itself a
replacement requirement rather than a missing screenshot.

This capture may use an isolated disposable database. It must not mutate the
developer’s normal financial workspace.
