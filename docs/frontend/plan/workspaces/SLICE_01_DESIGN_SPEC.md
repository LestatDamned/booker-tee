# Slice 1 Workspaces directory design specification

Статус: **UX/UI-контракт и visual prototype приняты 2026-08-03; production
runtime и replacement gate завершены**.
Документ уточняет принятые D1–D4, D10, D13 и D14 только на уровне presentation
и interaction. Он не меняет product policy, API authority или границы slices.

## 1. Evidence and design authority

Фактическая база:

- legacy composition, permission states и browser measurements:
  [`UX_AUDIT.md`](UX_AUDIT.md), `src/app/templates/workspaces/index.html`,
  `src/app/features/workspaces/router.py` и
  `src/app/features/workspaces/presentation/presenter.py`;
- accepted API/state boundary: [`API_AND_STATE.md`](API_AND_STATE.md);
- existing React composition and CSS ownership:
  `docs/design/UI_FOUNDATION.md`, `frontend/app/ui/` and
  `frontend/app/styles/tokens.css`;
- current create behavior selects the created workspace:
  `src/app/features/workspaces/router.py:create_workspace` and
  `WorkspaceService.create_for_user(...)`.

External guidance informs behavior, not Booker Tee branding:

- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines?lang=en):
  clear hierarchy, consistency across window sizes and familiar controls;
- [Material adaptive layout guidance](https://developer.android.com/codelabs/adaptive-material-guidance):
  layouts reflow by available window class and remain fluid between classes;
- [WAI-ARIA modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/):
  inert background, contained tab sequence, Escape, initial focus and focus
  return;
- [WCAG 2.2 target size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
  and [focus-visible guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html).

The `ui-ux-pro-max` review reinforced visible focus, async feedback, responsive
reflow, 44 px product targets and restrained motion. Its generated marketplace,
glassmorphism, palette and font recommendations are explicitly rejected:
Booker Tee semantic theme tokens, Inter typography and existing component
geometry remain authoritative.

## 2. User job and hierarchy

The page answers one high-risk question: **which workspace scopes the financial
application now, and where can the user switch safely?** Creation is the only
secondary page-level workflow.

Priority order:

1. identify the current financial context;
2. compare accessible workspaces;
3. switch with immediate pending feedback and a committed boundary reload;
4. create a workspace without losing the directory context.

Members, invitations, identity editing, lifecycle and activity are absent from
Slice 1. No disabled settings links or placeholder sections are rendered.

## 3. Canonical page composition

Proposed route: `GET /app/workspaces`.

```text
AppShell
└─ main
   └─ PageFrame
      └─ WorkbenchSurface: “Доступные пространства”
         ├─ WorkbenchHeader
         │  └─ PageHeader
         │     ├─ eyebrow: “Финансовый контекст”
         │     ├─ h1: “Пространства”
         │     ├─ description: current workspace + purpose of switching
         │     └─ primary CTA: “Создать пространство”
         ├─ WorkbenchStatus: count + explicit current workspace
         └─ ResponsiveRecordCollection
            ├─ expanded: semantic table
            └─ compact/medium: semantic ordered record list

create -> WorkbenchPanel on the right / full-width on a small phone
switch -> POST boundary mutation -> hard reload /app/workspaces
```

There is no search, filter, pagination, metrics strip or decorative hero in the
first slice. Current evidence shows a small private directory, and adding those
controls would increase decision cost without a proven retrieval problem. They
may be introduced only after measured list size or usability evidence.

## 4. Expanded layout

At widths above the existing `ResponsiveRecordCollection` breakpoint
(`64rem`), use one table with this visual and semantic order:

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ ФИНАНСОВЫЙ КОНТЕКСТ                                  [Создать пространство] │
│ Пространства                                                               │
│ Сейчас: Дом · Выберите контекст, в котором будут открываться финансы.       │
├────────────────────────────────────────────────────────────────────────────┤
│ 3 пространства · Текущее: Дом                                              │
├──────────────────────────┬────────────┬──────────────┬───────────┬─────────┤
│ Пространство             │ Тип/валюта│ Ваш доступ   │ Состояние │ Действие│
├──────────────────────────┼────────────┼──────────────┼───────────┼─────────┤
│ Дом                      │ Личное RUB│ Владелец     │ Текущее   │ —       │
│ Семейный бюджет          │ Общее RUB │ Редактор     │ Доступно  │ Перейти │
│ Архив проекта            │ Общее USD │ Наблюдатель  │ Неактивно │ —       │
└──────────────────────────┴────────────┴──────────────┴───────────┴─────────┘
```

Proposed column behavior:

- identity gets the flexible width and wraps; it is never ellipsized as the
  only way to recover the full name;
- type and currency use `Tag`/plain facts, not status color;
- membership role is server text and never used by React to derive authority;
- lifecycle/current state uses `StatusLabel` with visible text;
- only a selectable non-current record gets the primary row action `Перейти`;
  its accessible name is `Перейти в пространство «{name}»`;
- the current record has `aria-current="true"`, a restrained selection rail or
  surface and no disabled imitation button;
- inactive or server-blocked records remain non-interactive and show a safe
  blocking explanation only when the API says that explanation may be known.

The whole row is not clickable. This avoids nested targets and accidental
boundary switches while selecting text or using row metadata.

## 5. Medium and compact layout

At `64rem` and below, preserve the same information order in records:

```text
┌──────────────────────────────────────┐
│ Пространства                        │
│ Сейчас: Дом                         │
│ [Создать пространство]              │
├──────────────────────────────────────┤
│ Дом                       [Текущее]  │
│ Личное · RUB                         │
│ Ваш доступ: Владелец                 │
├──────────────────────────────────────┤
│ Семейный бюджет           [Доступно] │
│ Общее · RUB                          │
│ Ваш доступ: Редактор                 │
│ [Перейти в пространство]             │
└──────────────────────────────────────┘
```

- At 920 px the record list may retain inline action placement when 44 px
  targets and readable identity both fit; otherwise the action moves below the
  facts.
- At 390 px records are one column, action width follows the existing Button
  composition, and names wrap with `overflow-wrap:anywhere` as a last resort.
- The create panel is a right sheet on tablet/desktop and full viewport width at
  the existing `35rem` breakpoint. It uses `100dvh` and its own body scroll;
  page content does not create a second active scroll region.
- No page-level horizontal scrolling is allowed at 390 px, including 200%
  text zoom and long Russian names.

Desktop table and mobile list are projections of one loader dataset. Exactly
one projection is visible and operable at a time; hidden controls must not enter
the accessibility tree or tab order.

## 6. Ordering and record meaning

Proposed stable order:

1. current workspace;
2. other selectable active workspaces;
3. visible inactive/unselectable workspaces.

Within groups, the API supplies a deterministic order by normalized display
name with ID as a stable tie-breaker. React does not silently reorder after a
mutation. Personal and shared workspaces use identical geometry; only type copy
and server capabilities differ.

Directory items expose no member email, member count, invitation facts,
integration facts or audit history. A workspace record represents a financial
scope, not a generic CRUD entity.

## 7. Create panel

The `Создать пространство` CTA opens `WorkbenchPanel` titled
`Новое пространство` with concise copy: creation also makes the new workspace
current.

Field order:

1. `Название` — text input, initial focus, no placeholder-only label;
2. `Тип` — native select from server-provided fixed options;
3. `Основная валюта` — native select from server-provided fixed options;
4. actions: `Отмена`, `Создать и перейти`.

`SearchableSelect` is not used. The idempotency key belongs to the local draft
and is reused only when retrying the same normalized payload.

Interaction contract:

- pristine Escape/close/cancel closes and returns focus to the CTA;
- dirty dismissal asks whether to discard the draft; focus defaults to keeping
  the draft, not discarding it;
- submit disables all closing/submission paths that could duplicate the
  request and changes the button label to `Создаём…` with a spinner;
- `422` keeps values, shows `FormErrorSummary`, and focuses the first invalid
  field;
- recoverable network/server errors keep the draft and provide `Повторить`;
- committed success selects the new workspace and performs the same hard
  boundary reload as an explicit switch.

The feature must verify the existing `WorkbenchPanel` against the WAI-ARIA
dialog behavior instead of inventing a workspace-specific modal abstraction.

## 8. Switch interaction and boundary safety

The select action is a mutation, not navigation styling:

```text
activate “Перейти”
-> disable that action and announce “Переключаем пространство…”
-> POST /api/v1/workspaces/{id}/select
   with expectedCurrentWorkspaceId + CSRF
-> server validates active membership, locks session and commits
-> discard old workspace route data and local drafts
-> hard replace/reload /app/workspaces
-> focus h1 and announce the committed current workspace
```

No optimistic current marker is shown. Other select actions are disabled while
one switch is pending. A generic one-shot success notice may cross the reload,
but it must contain no financial data or old workspace cache.

Recovery:

- `409 workspace_switch_conflict`: reload authoritative directory/session,
  retain no stale selection and explain that another tab changed the context;
- masked missing/foreign/inactive outcome: use one safe message,
  `Пространство больше недоступно`, then refresh the directory;
- network failure before a committed response: keep the old workspace current
  and offer retry;
- ambiguous timeout: refetch `/api/v1/session` before offering a retry, because
  the server may already have committed the switch.

Switch confirmation appears only when a registered dirty draft would be lost.
The dialog names the consequence and defaults focus to `Остаться`. There is no
confirmation for a clean switch.

## 9. Page state matrix

| State | Presentation | Recovery/action |
| --- | --- | --- |
| Route loading | `RouteLoadingPage`, stable shell geometry | none until settled |
| Loaded | status + directory records | create/switch by capabilities |
| Minimum one-workspace | current record, no artificial onboarding card | create optional second workspace |
| Explicit no-workspace | `WorkbenchEmptyState`, clear recovery explanation | `Создать пространство`; never silent creation on GET |
| Route/network error | `RouteStatePage` or page-level `InlineNotice` | `Повторить` |
| Stale session/directory | local `RequestState` while refetching once | authoritative state or recoverable error |
| Switch pending | initiating row busy; all switch actions disabled | committed reload or scoped error |
| Create pending | panel remains modal and busy | committed reload or preserved draft |
| Forbidden/missing item | indistinguishable safe item outcome | directory refresh |
| Inactive item | textual status, no select action | no lifecycle action until Slice 6 |

Loading placeholders must reserve meaningful space and avoid decorative shimmer
for a response that normally settles quickly. A spinner/status is sufficient
for a local mutation; the interface never appears frozen.

## 10. Accessibility contract

- Route entry and post-boundary reload move focus to the `h1` or main content;
  the existing AppShell skip link remains first.
- DOM and visual reading order are identity, type/currency, role, status,
  action. CSS never reverses it.
- Native table semantics are retained on expanded screens; compact records use
  `ol`/`li` and headings. ARIA does not replace native semantics.
- Current, available and inactive are announced in text; color is secondary.
- Every interactive target is at least the Booker Tee 44 px product target,
  exceeding WCAG 2.2's 24 px minimum; adjacent actions keep at least an 8 px
  gap.
- Focus-visible uses the existing 3 px semantic focus token and is never
  suppressed by row or status styling.
- Normal Tab order is sufficient; no custom arrow-key grid behavior is added.
- Panel focus remains contained, Escape follows dirty-state policy, and close
  returns focus to its trigger. Confirmation defaults to the least destructive
  action.
- Pending and success messages use live status without stealing focus. Errors
  use alert/summary semantics only when immediate announcement is necessary.
- At 200% text zoom and 390 px width, content reflows without clipping; no
  meaning depends on hover/title text.
- Motion uses existing duration tokens only for state feedback and respects
  `prefers-reduced-motion`. Boundary navigation is never delayed for animation.

## 11. UI Foundation manifest

Reuse without workspace-specific copies:

- `PageFrame`, `WorkbenchSurface`, `WorkbenchHeader`, `PageHeader`;
- `WorkbenchStatus`, `ResponsiveRecordCollection`, `WorkbenchRow` where its
  semantics fit the record projection;
- `Button`, `ActionStack` only if a later record gains more than one action;
- `Tag`, `StatusLabel`;
- `WorkbenchPanel`, `Field`, `Fieldset`, `FormGrid`, `FormActions`,
  `FormErrorSummary`;
- `RouteLoadingPage`, `RouteStatePage`, `RequestState`, `InlineNotice`, Toast;
- `ConfirmationDialog` only for dirty-draft loss.

Feature-owned code owns workspace columns, copy, record ordering projection,
capability placement and responsive composition CSS. No new shared table/card,
generic CRUD schema renderer, palette, font family or raw color token is
proposed.

## 12. Design acceptance gate

Before React/API implementation is considered presentation-complete:

- normal, long-name, inactive, no-workspace, pending and conflict states pass at
  1440/920/390;
- keyboard-only create, cancel, dirty close, switch and conflict recovery pass;
- visible focus, screen-reader names/current state/live announcements pass;
- 200% zoom, reduced motion and no-horizontal-overflow pass;
- a switch cannot show the new current marker before the server commit;
- after switch/create, no old workspace draft or response can repopulate UI;
- owner/admin/editor/uploader/analyst/viewer records render server capabilities
  without client role inference;
- no settings, members, invitations, lifecycle or legacy deletion leaks into
  Slice 1.

The contract is accepted and implemented. The standalone visual review artifact
is [`prototype/index.html`](prototype/index.html). Production evidence lives in
`frontend/app/features/workspaces/`, `tests/api/test_workspaces_api.py`,
`tests/features/workspaces/test_workspace_slice01_*` and
`scripts/workspaces_slice01_browser.py`.
