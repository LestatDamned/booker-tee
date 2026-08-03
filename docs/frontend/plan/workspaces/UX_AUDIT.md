# Workspaces UX/UI audit

Статус: factual static audit + proposed React composition. Browser screenshots
не создавались на read-only этапе: существующий `scripts/ui_audit.py` готовит
realistic state через signup и mutations. Это отмечено как verification blocker,
а не заменено предположением.

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
  transitions, but no current stored workspace screenshot or measured overflow
  result exists in the repository.

### Geometry risks

- 920 px immediately collapses actions under every record, increasing vertical
  height for members/invitations/workspaces.
- The legacy full-width action column can create repeated loud buttons; current
  React `ActionStack orientation="row"` is a better proven compact contract.
- One-time invitation link/copy correctly collapses from two columns, but long
  credential text requires `overflow-wrap`/scroll testing at 390 px.
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
- Error summary focuses first invalid field; `409` notice keeps draft and offers
  reload/retry/discard.
- Toast uses polite live status and never steals focus.
- At 390 px no horizontal page overflow; long workspace names, emails and invite
  links wrap or use an explicitly accessible disclosure.
- Reduced motion applies to row highlight/panel transitions.

## Required browser baseline before implementation

Before changing presentation, capture current SSR at 1440/920/390 for:

1. owner with multiple workspaces, members, pending invites and activity;
2. admin/member/viewer permissions;
3. create/edit expanded states;
4. one-time invitation link;
5. invalid/expired invitation preview;
6. long names/emails and empty/minimal workspace.

This capture may use an isolated disposable database. It must not mutate the
developer’s normal financial workspace.

