# Review Item CSS Migration Plan

Status: historical planning document for the legacy frontend. Do not use it as
the CSS migration plan for Frontend Next. No production CSS, templates, Python,
or runtime contracts are changed by this file.

This plan uses the CSS audit in [`css-audit.md`](css-audit.md), the design
direction in [`design/DESIGN.md`](design/DESIGN.md), and the historical legacy
import-review contract in
[`design/REFACTOR_PROJECT_DESIGN.md`](design/REFACTOR_PROJECT_DESIGN.md).

For active frontend CSS architecture, use
[`design/FRONTEND_NEXT_DESIGN.md`](design/FRONTEND_NEXT_DESIGN.md) and
[`design/WORKBENCH_ROW_DESIGN.md`](design/WORKBENCH_ROW_DESIGN.md).

## Goal

Pilot a safe migration of the import Review Item from a legacy mixed selector
stack to a stable BEM-style component contract, with semantic tokens and a
future component CSS module, while preserving the current Jinja, ViewModel,
HTMX, and Alpine behavior.

Non-goals for the pilot:

- no mass CSS tokenization;
- no deletion of legacy selectors;
- no redesign of review workflows;
- no change to `ReviewItemVM`, action policy, or status resolution semantics;
- no new frontend framework.

## Component Scope

### Review Item Files

| File | Lines | Role | Ownership |
| --- | ---: | --- | --- |
| `src/app/templates/imports/review.html` | 15-20, 27-29 | Renders `review_items` inside `.review-list`; loads `import-review-scroll.js`. | Page owner, not Review Item component. |
| `src/app/templates/imports/review/_item.html` | 1-128 | Main Review Item DOM, HTMX target, Alpine panel state, action summary, panels. | Pilot component root. |
| `src/app/templates/imports/review/_action_set.html` | 1-60 | Review Item action layout around shared `ui/_action.html`. | Review Item-adjacent subcomponent. |
| `src/app/templates/ui/_action.html` | 1-51 | Shared action button/form/link/panel-toggle renderer. | Shared UI, do not migrate inside pilot. |
| `src/app/templates/imports/review/_panel_tab.html` | 1-16 | Category/transfer panel tab. | Review Item subcomponent. |
| `src/app/templates/imports/review/_panel_drawer.html` | 1-14 | Lazy-loaded panel drawer host. | Review Item subcomponent. |
| `src/app/templates/imports/review/_panel_content.html` | 1-6 | Panel payload placeholder/content switch. | Review Item subcomponent. |
| `src/app/templates/imports/review/_category_panel.html` | 3-44 | Category form payload. | Panel payload, keep legacy-compatible. |
| `src/app/templates/imports/review/_transfer_panel.html` | 3-69 | Transfer form payload with local Alpine state. | Panel payload, keep legacy-compatible. |
| `src/app/templates/imports/review/_category_dialog.html` | 1-46 | Dialog opened from category panel error/editor state. | Panel payload dependency. |
| `src/app/templates/imports/_review_action_response.html` | 1-10 | HTMX response: current item plus queue bar and OOB sibling items. | Response shell, not component CSS owner. |
| `src/app/features/imports/presentation/review/models.py` | 97-108, 260-292 | `ReviewPanelVM` and `ReviewItemVM` fields used by templates. | Presentation contract. |
| `src/app/features/imports/presentation/review/item.py` | 154-282, 396-404, 415-418 | Builds `ReviewItemVM`, visual state, panels, summaries, tones. | Presentation owner. |
| `src/app/features/imports/presentation/review/state.py` | 10-15, 70-142 | Final statuses, confirmability, visual state resolver. | State semantics owner. |
| `src/app/features/imports/presentation/review/actions.py` | 26-142, 169-301 | Action policy and action ids/placements. | Action semantics owner. |
| `src/app/features/imports/presentation/review/panels.py` | 47-163 | Category/transfer panel payloads and URLs. | Panel payload owner. |
| `src/app/features/imports/routes/review.py` | 40-84, 87-150, 153-203, 214-292 | Page render, status actions, lazy panel endpoint, undo, category creation. | Routing/HTMX owner. |
| `src/app/features/imports/routes/review_responses.py` | 21-116, 124-243 | HTMX response state and OOB item refreshes. | Response owner. |
| `src/app/static/js/import-review-scroll.js` | 1-129 | Scroll preservation keyed by `.review-item`. | JS dependency; selector-sensitive. |
| `src/app/static/js/entity-target.js` | 1-127 | Working/target feedback for `[data-entity-working="true"]`. | Shared JS dependency. |
| `src/app/static/css/app.css` | 5001-6705, 6813-7550 | Current Review Item, panels, actions, responsive CSS. | Legacy CSS source during transition. |

### Dependency Classes

Own, movable into future Review Item module:

- `.review-item`, `.review-item--vm`, `.review-item--next`,
  `.review-item--status-*`;
- `.review-item__main`, `__topline`, `__meta`, `__row-index`, `__date`,
  `__date-label`, `__account`, `__amount`, `__description`;
- `.review-item__state`, `__state-primary`, `__state-secondary`,
  `__state-token`;
- `.review-item__signals`, `__signal`, `__signal--proposal`,
  `__signal--problem`;
- `.review-item__actions`, `__panels`, `__panel-tabs`, `__panel-drawers`;
- `.review-item__ledger-summary`, `__ledger-meta`, `__ledger-type`,
  `__ledger-status`, `__ledger-title`.

Shared, do not move in the first pilot:

- `.financial-row`, `.financial-row__main`, `__topline`, `__meta`, `__date`,
  `__amount`, `__description`, `__side`, `__drawer`, `__result-card`;
- `.money-value`, `.money-income`, `.money-expense`, `.money-transfer`;
- `.button`, `.button-small`, `.button-danger`;
- `.ui-action__*`, `.action-form*`, `.action-button`, `.action-label`,
  `.action-primary`, `.action-secondary`, `.action-danger`;
- `.row-drawer`, `.row-drawer__form`, `.row-drawer__field`,
  `.row-drawer__footer`;
- generic form controls: `.field`, `.input`, `.select`;
- global state/utility selectors: `[x-cloak]`, `.entity-card--working`,
  `html:not(.entity-target-cleared) ...:target`.

Global/page dependencies:

- `.import-review-page`, `.review-list`, `.review-queue-*`;
- page shell `.panel`, `.stack`;
- responsive media rules in `app.css:6813-7550`.

Dynamic/VM-owned dependencies:

- `review-item--status-{{ item.visual_state }}`;
- `{{ item.money_tone }}` with values from `ReviewMoneyTonePresenter`;
- `tone-{{ item.state_badge.tone }}`;
- `tone-{{ item.classification_badge.tone }}`;
- `problem-{{ problem.tone }}`;
- `review-panel__tab--{{ panel.role }}`;
- `review-panel__tab--{{ panel.panel_type }}`;
- `review-panel__drawer--{{ panel.panel_type }}`;
- `review-item__ledger-summary--{{ action_summary.tone }}`;
- `tone-{{ action_summary.type_value }}`;
- `ui-action__button--{{ action.placement }}`,
  `ui-action__button--{{ action.id }}`,
  `action-{{ action.placement }}`, `action-{{ action.id }}`.

Unknown or unstable dependencies to verify with fixtures:

- whether `RawTransactionStatus.EXTRACTED` can appear on the review page;
- whether `RawTransactionStatus.NORMALIZED` should ever remain visible as a
  visual state. Current resolver maps confirmable normalized rows to
  `ready_to_confirm`, otherwise `needs_review`;
- exact fixture coverage for failed rows with only `normalization_error`;
- whether category dialog error state appears inside lazy-loaded panel content
  or only after action response.

## Current DOM Contract

### Root And Behavior

```text
article#{{ item.anchor_id }}
  class="
    financial-row
    review-item
    review-item--vm
    review-item--status-{{ item.visual_state }}
    review-item--next?
  "
  data-entity-working="true"
  hx-boost="true"
  hx-select="#{{ item.anchor_id }}"
  hx-target="#{{ item.anchor_id }}"
  hx-swap="outerHTML show:none"
  hx-push-url="false"
  x-data="{ activePanel, togglePanel, openCategoryDialog }"
  hx-swap-oob="true"?
```

Data source:

- `item.anchor_id`, `item.visual_state`, `item.is_next`, `item.oob`;
- HTMX values are static template contract;
- Alpine initial state comes from `item.initial_active_panel_id`.

DOM dependency notes:

- `import-review-scroll.js` queries `.review-item`, so the class must remain
  until that JS is updated.
- `entity-target.js` queries `[data-entity-working="true"]` and applies
  `.entity-card--working`; do not remove the data attribute.
- `hx-select` and `hx-target` depend on a stable root `id`.
- OOB replacement depends on `_review_action_response.html` including
  `_item.html` with `review_item_oob = true`.

### DOM Tree

```text
article.financial-row.review-item.review-item--vm.review-item--status-{state}
  div.financial-row__main.review-item__main
    div.financial-row__topline.review-item__topline
      div.financial-row__meta.review-item__meta
        span.review-item__row-index
          strong "#"
          text item.row_index
        span.financial-row__date.review-item__date
          span.review-item__date-label
          strong item.date_label
        span.review-item__account item.account_label
      span.financial-row__amount.review-item__amount.money-value.{money_tone}
        text item.amount_label
        small item.currency
    div.financial-row__description.review-item__description item.description
    if no action_summary and any state/classification/source badge:
      div.review-item__state
        div.review-item__state-primary
          span.review-item__state-token.tone-{state_badge.tone}
          span.review-item__state-token.tone-{classification_badge.tone}
        if classification_source_badge:
          div.review-item__state-secondary
            span item.classification_source_badge.label
    if proposal_summary or problems:
      div.review-item__signals
        if proposal_summary:
          span.review-item__signal.review-item__signal--proposal
        for problem:
          span.review-item__signal.review-item__signal--problem.problem-{problem.tone}
  div.financial-row__side.review-item__actions
    if action_summary:
      div.financial-row__result-card.review-item__ledger-summary.review-item__ledger-summary--{tone}
        div.review-item__ledger-meta
          if type:
            span.review-item__ledger-type.tone-{type_value}
          span.review-item__ledger-status
        div.review-item__ledger-title
    include imports/review/_action_set.html
  if item.panels:
    div.financial-row__drawer.review-item__panels
      div.review-panel__tabs.review-item__panel-tabs
        button.review-panel__tab.review-panel__tab--{role}.review-panel__tab--{panel_type}
      div.review-panel__drawers.review-item__panel-drawers
        div.row-drawer.review-panel__drawer.review-panel__drawer--{panel_type}
          include imports/review/_panel_content.html
```

Conditions and ownership:

| DOM area | Condition | Data source | CSS owner now | Pilot owner |
| --- | --- | --- | --- | --- |
| Root state | Always | `item.visual_state` | `.review-item--status-*` | New state contract plus legacy mirror. |
| Next marker | `item.is_next` | `ReviewQueuePresenter` via presenter deps | `.review-item--next` | Keep legacy, add `review-item--is-next`. |
| Topline/meta | Always | `ReviewItemVM` fields | `financial-row` plus `review-item` | Component owns layout refinements, shared row remains. |
| Money tone | Always if tone present | `ReviewMoneyTonePresenter.tone` | shared money classes | Keep shared. |
| State badges | No `action_summary`; any badge exists | presenter badges | `review-item__state*`, `.tone-*` | Component owns badge container, tokens own tone values. |
| Signals | Proposal or problems | `proposal_summary`, `problems` | `review-item__signals`, `.problem-*` | Component owns signal layout; tone tokens own colors. |
| Ledger summary | `operation_link` or `outcome_summary` | presenter | `review-item__ledger-*` | Component owns. |
| Actions | Always via action set | action policy | shared action plus review action wrappers | Wrapper only in pilot. |
| Panels | `item.panels` | presenter `visible_panels` | `review-panel*`, row drawer | Keep compatibility; migrate after root stable. |
| Lazy panel content | panel payload may be `None` | panel presenter/routes | `data-review-panel-*` + Alpine | Behavior contract, not CSS. |

## Visual States

### Source Of Truth

`RawTransactionStatus` currently has these values:

```text
extracted, normalized, suggested, needs_review, matched, ignored, duplicate,
possible_duplicate, failed, confirmed
```

`ReviewStateResolver.resolve` maps rows to Review Item visual state:

| Condition | Visual state |
| --- | --- |
| Raw status in `{confirmed, matched, ignored, duplicate}` | same status value |
| Raw status `failed` or row has `normalization_error` | `failed` |
| Raw status `possible_duplicate` | `possible_duplicate` |
| Active rule/system suggestion | `suggested` |
| Confirmability policy passes | `ready_to_confirm` |
| Fallback | `needs_review` |

There is no separate current `parse_error` visual state in code. The design doc
mentions `failed / parse_error`; for the current component contract, represent
that as `failed` unless code changes first.

### State Matrix

| Visual state | Domain source | Badges/signals | Panels | Primary action | Secondary/menu/danger | CSS today |
| --- | --- | --- | --- | --- | --- | --- |
| `needs_review` | fallback or validation problems | state badge, classification badge, problems | category + transfer | panel toggle "Разобрать" | transfer, needs_review, ignore | `.review-item--status-needs_review`, `.tone-needs_review` |
| `ready_to_confirm` | confirmability passes | state/classification badges | category + transfer | confirm | fix category, transfer, needs_review, ignore | `.review-item--status-ready_to_confirm` |
| `suggested` | active rule/system suggestion | outcome summary, proposal may be hidden by final/action summary rules | category + transfer | confirm | fix category, transfer, needs_review, ignore | `.review-item--status-suggested`, `.tone-suggested` |
| `possible_duplicate` | raw status possible duplicate | state badge, problems | category + transfer | mark unique | needs_review, ignore | `.review-item--status-possible_duplicate`, `.tone-possible_duplicate` |
| `duplicate` | final raw status duplicate | state badge | category + transfer | open operation or mark unique | needs_review, ignore | `.review-item--status-duplicate`, `.tone-duplicate` |
| `confirmed` | final raw status confirmed | ledger summary | no panels | none | undo posting in correction/danger flow | `.review-item--status-confirmed` |
| `matched` | final raw status matched | ledger summary | no panels | none | undo posting in correction/danger flow | `.review-item--status-matched` |
| `ignored` | final raw status ignored | state badge | category + transfer | restore | details | `.review-item--status-ignored` |
| `failed` | raw status failed or normalization error | state badge, problems | category + transfer | panel toggle "Разобрать" | transfer, needs_review, ignore | `.review-item--status-failed`, `.tone-failed` |
| `parse_error` | design-language alias only | should map to failed today | not applicable | not applicable | not applicable | no current selector |

Notes:

- `matched` is both a `RawTransactionStatus` and a final visual state.
- `normalized` exists as a raw status and label, but is not a stable visual state
  in the current resolver. The legacy CSS still has
  `.review-item--status-normalized`; keep it until screenshots prove it is dead.
- `suggested` means an active suggestion, not merely "has a category value".

## Current CSS Influence

### Selector Counts

Counts are selector occurrences in `src/app/static/css/app.css`, not declarations.
They were gathered from the CSS file during this planning pass.

| Area | Count | Line range | Migration note |
| --- | ---: | ---: | --- |
| Review-area total selectors | 640 | 5000-7550 | Broad import/review page area. |
| Review-area unique selectors | 548 | 5000-7550 | Includes page tools, dialogs, forms, responsive rules. |
| Direct `.review-item*` selectors | 82 | 5286-7542 | First pilot target. |
| `.review-panel*` selectors | 29 | 5559-7436 | Keep compatible; migrate after root. |
| `.review-actions*`/action wrappers | 40 | 5535-6987 | Shared partial dependency; wrapper-only pilot. |
| `.financial-row*` selectors in review area | 30 | 5113-6976 | Shared row pattern, not pilot-owned. |
| `.ui-action*`/legacy action selectors | 26 | 6255-7290 | Shared action partial, not pilot-owned. |
| Panel form selectors | 31 | 6303-7436 | Payload forms, later migration. |
| Category dialog selectors | 12 | 6569-6681 | Dialog dependency, later migration. |
| Problem/signal selectors | 6 | 5487-5522 | Pilot can wrap; tone values should become tokens. |
| Money/tone selectors local to item state | 8 | 5463-5481 | Convert to semantic component vars later. |

Direct plus indirect component selectors from the broader scan:

- direct Review Item/action/panel-related selector occurrences: 175;
- shared selector occurrences touching the same stack: 311;
- combined selectors that mix direct and shared classes: 29.

The combined selectors are the main deletion risk because they tie component
markup to shared primitives, for example:

- `.review-item--vm .review-item__meta > .financial-row__date`;
- `.review-actions__menu .ui-action__form`;
- `.review-item__actions .ui-action__button`;
- `.review-item__actions .button`;
- `.review-panel-form .row-drawer__field`;
- `.review-item__state-token.tone-*`.

### CSS Blocks

| Lines | Scope | Specificity profile | `!important` | Move/delete recommendation |
| ---: | --- | --- | --- | --- |
| 5001-5113 | Review page/list/queue shell | Mostly class selectors | no | Keep page-level; not part of pilot component. |
| 5115-5286 | `.financial-row` shared row pattern | Class + descendant selectors | no | Do not move; pilot can temporarily rely on it. |
| 5288-5326 | Review Item root, status, target, next | Single class; target selector `0,3,1` | no | Add new aliases first, do not delete old. |
| 5328-5419 | Review Item meta/date/amount/description | Descendant/child selectors up to `0,3,1` | no | Pilot-owned but preserve DOM-sensitive child selectors. |
| 5421-5487 | State badge/token/tone styling | Single class and compound tone selectors | no | Pilot-owned; map tones to semantic vars. |
| 5489-5527 | Signals/problems/actions start | Single class selectors | yes on problem tones | Pilot-owned with caution. |
| 5529-5559 | Review Item actions and panels wrappers | Single class + form descendant | no | Wrapper migration only. |
| 5561-5633 | Review panel tabs/drawers heading | Class/attribute selectors | no | Keep compatible; panel-specific later. |
| 5635-5769 | Danger zone/action accordion details | Shared action menu selectors | no | Do not move in first pilot. |
| 6202-6267 | Review action details/menu | Mixed shared/review selectors | no | Do not split before action partial contract. |
| 6269-6296 | Review panel drawer/body | Class and pseudo-element | yes on drawer width/margin | Later panel migration. |
| 6305-6429 | Review panel forms/grids/rule strip | Mixed shared form selectors | no | Later panel payload migration. |
| 6432-6512 | Primary/secondary/review action buttons | Mixed `.review-item__actions` + `.ui-action` + `.button` | no | Keep old and add new wrapper classes only. |
| 6514-6569 | Ledger summary | Component-local | no | Good pilot candidate. |
| 6571-6705 | Category dialog/remember transfer controls | Dialog/form local | no | Out of first root pilot. |
| 6813-7550 | Responsive overrides | Mixed page and component selectors | yes in mobile form grid | Mirror any new selectors here before old deletion. |

### `!important` Risk

In the review area:

- `app.css:5520-5521` forces `.problem-warning` border/color;
- `app.css:5525-5526` forces `.problem-danger` border/color;
- `app.css:6272,6274` forces `.review-panel__drawer` width/margin;
- `app.css:6866` and `7429` force mobile grid placement.

The pilot should not add new `!important`. Replace only after visual regression
shows the new selector order and specificity are sufficient.

## `financial-row` Dependency Analysis

Review Item is currently not a standalone component. It is a specialization of
the shared financial row pattern:

- root carries both `.financial-row` and `.review-item`;
- main content uses `.financial-row__main`, `__topline`, `__meta`, `__date`,
  `__amount`, `__description`;
- side area uses `.financial-row__side`;
- panels use `.financial-row__drawer`;
- ledger result uses `.financial-row__result-card`.

This pattern is shared with manual operations, account movements, categories,
properties, workspaces, transaction rules, and raw transaction cards. Moving
`financial-row` into Review Item would create cross-feature regressions.

Pilot recommendation:

1. Keep all `financial-row*` classes in markup.
2. Add new Review Item BEM aliases next to them.
3. In the future component CSS module, style Review Item through the new
   aliases while leaving `financial-row` as a shared fallback.
4. Delete combined selectors only after screenshots pass for other
   `financial-row` consumers.

## Shared Action Partial Analysis

`imports/review/_action_set.html` owns action grouping:

- `.review-actions__system`;
- `.review-actions__row`;
- `.primary-actions`;
- `.secondary-actions`;
- `.review-actions__secondary`;
- `.review-actions__details`;
- `.review-actions__correction`;
- `.review-actions__menu`;
- `.review-actions__menu-section`;
- `.review-actions__danger-zone`;
- `.review-actions__danger-direct`.

`ui/_action.html` owns actual action element classes:

- form: `.ui-action__form`, `.ui-action__form--{placement}`,
  `.ui-action__form--{id}`, `.action-form`, `.action-form-{placement}`,
  `.action-form-{id}`;
- button/link/panel toggle: `.button`, `.button-small`, `.ui-action__button`,
  `.ui-action__button--{placement}`, `.ui-action__button--{id}`,
  `.action-button`, `.action-{placement}`, `.action-{id}`,
  `.primary-action?`, `.button-danger?`;
- label: `.action-label`, `.ui-action__label`.

This partial is reused outside Review Item. The pilot must not rename its shared
classes. If Review Item needs BEM action hooks, add wrappers in
`_action_set.html`, not inside `ui/_action.html`, unless a separate UI action
migration is planned.

Recommended transitional wrappers:

- `review-item__action-system` alongside `.review-actions__system`;
- `review-item__action-row` alongside `.review-actions__row`;
- `review-item__primary-actions` alongside `.primary-actions`;
- `review-item__secondary-actions` alongside `.secondary-actions`;
- `review-item__action-menu` alongside `.review-actions__menu`;
- `review-item__danger-zone` alongside `.review-actions__danger-zone`.

## HTMX And Alpine Analysis

### HTMX Scenarios

| Scenario | Current contract | Migration risk |
| --- | --- | --- |
| Status action submit | `hx-boost=true` on root boosts forms; response selects root by `id` and swaps `outerHTML`. | Removing root `id`, `hx-*`, or changing nesting around forms breaks row refresh. |
| Error response | Router returns same `_review_action_response.html` with `action_error` and active panel type. | CSS must preserve opened panel layout after failed submit. |
| OOB sibling updates | Response includes `oob_review_items` with `hx-swap-oob=true`. | New root aliases must be present in both normal and OOB render. |
| Queue bar update | Response includes `_queue_bar.html` separately. | Review Item CSS must not assume queue DOM lives inside item. |
| Lazy panel load | Alpine calls `window.htmx.ajax("GET", loadUrl, { target: drawer, swap: "innerHTML" })`. | Drawer data attributes and `id`/panel relation must remain stable. |
| Non-HTMX fallback | Router redirects to document review page. | Markup must remain complete on full page render. |

### Alpine Scenarios

Root `_item.html` local state:

- `activePanel`;
- `togglePanel(panelId)`;
- `openCategoryDialog()`;
- lazy panel loading state via `data-review-panel-loaded`.

Panel tab:

- `x-bind:aria-expanded`;
- `x-bind:class="{ 'is-active': activePanel === panel.id }"`;
- `@click="togglePanel(panel.id)"`;
- open/close labels via `x-show`.

Panel drawer:

- `x-show="activePanel === panel.id"`;
- `x-cloak`;
- `style="display: none;"` when not initially open.

Transfer panel:

- local `x-data="{ selectedAccount: '', transferMatch: 'new' }"`;
- `x-model`, `x-show`, `x-bind:hidden`, `x-bind:disabled`.

Category dialog:

- `x-ref="categoryDialog"`;
- optional `x-init` opens dialog on create-category error.

Pilot rule: do not rename Alpine state keys, `x-ref`, panel ids, or
`data-review-panel-*` attributes during CSS migration.

## Local Values Inventory

### Existing Component-Relevant Values

Current values are mostly hard-coded against global tokens:

- surfaces: `--surface`, `--surface-strong`, `--bg`;
- borders: `--border`;
- text: `--text`, `--muted`;
- semantic colors: `--accent`, `--green`, `--danger`, `--warning`, `--help`;
- spacing: mixed literal `0.35rem`, `0.5rem`, `0.65rem`, `0.75rem`, `0.85rem`,
  `0.9rem`, `1rem`, `1.15rem`, `1.25rem`;
- radius: inherited from old design, mostly local literal values in CSS;
- typography: `.financial-row__date` and `.financial-row__amount` shared scale,
  Review Item local adjustments for meta/date/account.

### Unique `color-mix(...)` Values In Review Item/Panel/Action Area

The scoped range `app.css:5286-6562` contains 73 unique `color-mix(...)`
expressions and 101 total occurrences. Unique values:

```css
color-mix(in srgb, var(--surface) 88%, var(--accent))
color-mix(in srgb, var(--accent) 42%, var(--border))
color-mix(in srgb, var(--accent) 12%, var(--surface-strong))
color-mix(in srgb, var(--accent) 86%, var(--muted))
color-mix(in srgb, var(--accent) 78%, var(--muted))
color-mix(in srgb, var(--surface-strong) 48%, transparent)
color-mix(in srgb, var(--green) 78%, var(--border))
color-mix(in srgb, var(--danger) 78%, var(--border))
color-mix(in srgb, var(--accent) 78%, var(--border))
color-mix(in srgb, var(--warning) 78%, var(--border))
color-mix(in srgb, var(--surface-strong) 40%, transparent)
color-mix(in srgb, var(--accent) 58%, var(--border))
color-mix(in srgb, var(--accent) 6%, transparent)
color-mix(in srgb, var(--warning) 4%, transparent)
color-mix(in srgb, var(--border) 78%, transparent)
color-mix(in srgb, var(--surface-strong) 34%, transparent)
color-mix(in srgb, var(--accent) 62%, var(--border))
color-mix(in srgb, var(--accent) 13%, var(--surface-strong))
color-mix(in srgb, var(--muted) 84%, var(--border))
color-mix(in srgb, var(--danger) 42%, var(--border))
color-mix(in srgb, var(--danger) 5%, transparent)
color-mix(in srgb, var(--muted) 86%, var(--border))
color-mix(in srgb, var(--border) 42%, transparent)
color-mix(in srgb, var(--surface-strong) 30%, transparent)
color-mix(in srgb, var(--surface) 14%, transparent)
color-mix(in srgb, var(--accent) 52%, transparent)
color-mix(in srgb, var(--help) 24%, var(--border))
color-mix(in srgb, var(--help) 7%, transparent)
color-mix(in srgb, var(--surface-strong) 64%, var(--bg))
color-mix(in srgb, var(--surface-strong) 76%, var(--accent))
color-mix(in srgb, var(--accent) 74%, var(--muted))
color-mix(in srgb, var(--border) 46%, transparent)
color-mix(in srgb, var(--surface-strong) 62%, var(--bg))
color-mix(in srgb, var(--accent) 48%, var(--border))
color-mix(in srgb, var(--surface-strong) 72%, var(--accent))
color-mix(in srgb, var(--surface-strong) 20%, transparent)
color-mix(in srgb, var(--border) 34%, transparent)
color-mix(in srgb, var(--border) 58%, transparent)
color-mix(in srgb, var(--surface) 82%, var(--surface-strong))
color-mix(in srgb, var(--accent) 16%, var(--surface-strong))
color-mix(in srgb, var(--border) 28%, transparent)
color-mix(in srgb, var(--surface) 22%, transparent)
color-mix(in srgb, var(--text) 84%, var(--muted))
color-mix(in srgb, var(--surface-strong) 18%, transparent)
color-mix(in srgb, var(--accent) 82%, var(--muted))
color-mix(in srgb, var(--accent) 10%, transparent)
color-mix(in srgb, var(--surface-strong) 22%, transparent)
color-mix(in srgb, var(--muted) 82%, var(--accent))
color-mix(in srgb, var(--accent) 56%, var(--border))
color-mix(in srgb, var(--border) 60%, transparent)
color-mix(in srgb, var(--surface-strong) 16%, transparent)
color-mix(in srgb, var(--border) 66%, transparent)
color-mix(in srgb, var(--accent) 34%, var(--border))
color-mix(in srgb, var(--accent) 72%, var(--border))
color-mix(in srgb, var(--accent) 7%, transparent)
color-mix(in srgb, var(--border) 72%, transparent)
color-mix(in srgb, var(--help) 30%, var(--border))
color-mix(in srgb, var(--help) 72%, var(--border))
color-mix(in srgb, var(--help) 6%, transparent)
color-mix(in srgb, var(--text) 76%, var(--help))
color-mix(in srgb, var(--green) 76%, var(--border))
color-mix(in srgb, var(--green) 13%, var(--surface-strong))
color-mix(in srgb, var(--green) 18%, var(--surface-strong))
color-mix(in srgb, var(--accent) 26%, var(--border))
color-mix(in srgb, var(--surface-strong) 54%, transparent)
color-mix(in srgb, var(--danger) 68%, var(--border))
color-mix(in srgb, var(--danger) 7%, transparent)
color-mix(in srgb, var(--surface-strong) 28%, transparent)
color-mix(in srgb, var(--border) 80%, transparent)
color-mix(in srgb, var(--surface-strong) 52%, transparent)
color-mix(in srgb, var(--accent) 8%, var(--surface-strong))
color-mix(in srgb, var(--green) 78%, var(--muted))
color-mix(in srgb, var(--accent) 84%, var(--muted))
```

Color-mix risks:

- many values encode component semantics only by percentage, not by name;
- accent-heavy mixes will be hard to retheme without accidental contrast loss;
- warning/danger problem colors are enforced by `!important`;
- panel and action values are mixed into the same block as root Review Item
  values, so moving everything at once would create a large visual diff.

## Minimal Token Foundation

For the first Review Item pilot, define only component-level aliases in the
future CSS module. Do not create a global token taxonomy yet.

Suggested local custom properties:

```css
.review-item {
  --review-item-bg: var(--surface);
  --review-item-bg-strong: var(--surface-strong);
  --review-item-border: var(--border);
  --review-item-text: var(--text);
  --review-item-muted: var(--muted);
  --review-item-accent: var(--accent);
  --review-item-success: var(--green);
  --review-item-warning: var(--warning);
  --review-item-danger: var(--danger);
  --review-item-help: var(--help);
  --review-item-radius: 0.75rem;
  --review-item-gap: 0.75rem;
  --review-item-chip-bg: color-mix(in srgb, var(--review-item-bg-strong) 48%, transparent);
  --review-item-border-muted: color-mix(in srgb, var(--review-item-border) 78%, transparent);
}
```

Only after this pilot stabilizes, promote recurring aliases into global
semantic tokens such as `--status-warning-border` or
`--action-primary-surface`.

## Future BEM Contract

Use hyphenated state names for CSS, while preserving underscore VM values in
data attributes.

Root:

```text
review-item
review-item--state-needs-review
review-item--state-ready-to-confirm
review-item--state-suggested
review-item--state-possible-duplicate
review-item--state-duplicate
review-item--state-confirmed
review-item--state-matched
review-item--state-ignored
review-item--state-failed
review-item--is-next
review-item--has-panels
review-item--has-summary
```

Elements:

```text
review-item__body
review-item__main
review-item__topline
review-item__meta
review-item__meta-item
review-item__row-index
review-item__date
review-item__account
review-item__money
review-item__amount
review-item__currency
review-item__description
review-item__status
review-item__status-primary
review-item__status-secondary
review-item__status-token
review-item__signals
review-item__signal
review-item__signal--proposal
review-item__signal--problem
review-item__ledger-summary
review-item__ledger-meta
review-item__ledger-type
review-item__ledger-status
review-item__ledger-title
review-item__actions
review-item__action-system
review-item__action-row
review-item__primary-actions
review-item__secondary-actions
review-item__action-menu
review-item__danger-zone
review-item__panels
review-item__panel-tabs
review-item__panel-drawers
```

Panel contract, later migration:

```text
review-panel
review-panel--type-category
review-panel--type-transfer
review-panel--role-primary
review-panel--role-alternative
review-panel__tabs
review-panel__tab
review-panel__tab--is-active
review-panel__drawer
review-panel__body
review-panel__form
review-panel__grid
review-panel__footer
```

## Modifier Vs `data-state`

Recommendation: use both during transition, with different responsibilities.

- Keep modifier classes for CSS compatibility and low-cost styling:
  `.review-item--state-ready-to-confirm`.
- Add `data-state="{{ item.visual_state }}"` as the canonical machine-readable
  state for tests, JS, and future low-specificity selectors.
- Keep legacy `.review-item--status-{{ item.visual_state }}` until old CSS is
  deleted.

Why:

- current VM values use underscores, while target CSS should prefer hyphenated
  class names;
- data attributes avoid proliferating selectors for tests and screenshots;
- legacy status classes are already used and should not be removed in the same
  commit as new classes.

Transitional example:

```jinja
<article
  class="
    financial-row
    review-item
    review-item--vm
    review-item--status-{{ item.visual_state }}
    review-item--state-{{ item.visual_state | replace('_', '-') }}
    {% if item.is_next %}review-item--next review-item--is-next{% endif %}
    {% if item.panels %}review-item--has-panels{% endif %}
    {% if action_summary %}review-item--has-summary{% endif %}
  "
  data-state="{{ item.visual_state }}"
>
```

## Transitional Contract

First migration commit should only add aliases; it should not remove or restyle
legacy selectors.

Keep:

- `.financial-row*`;
- `.review-item--status-*`;
- `.review-item--vm`;
- `.review-item--next`;
- `.review-panel__*`;
- `.review-actions__*`;
- `.ui-action__*`;
- `.action-*`;
- `.button*`;
- `.problem-*`;
- `.tone-*`;
- `.money-*`.

Add:

- `data-state`;
- `review-item--state-*` aliases;
- `review-item--is-next`;
- `review-item--has-panels`;
- `review-item--has-summary`;
- optional new element aliases only where they do not make markup noisy.

Delete later, only after screenshots and selector-use checks:

- `.review-item--status-*`;
- `.review-item--vm`;
- direct `.review-item__state-token.tone-*` color styling, once tokenized;
- combined `.review-item__actions .button` and `.review-item__actions
  .ui-action__button` selectors, once action wrapper CSS exists;
- unused `.review-item--status-normalized`, if fixtures prove it unreachable.

## Future CSS Module Skeleton

Do not create this file in the current planning step. Candidate path:

```text
src/app/static/css/components/review-item.css
```

Skeleton:

```css
/* Review Item component.
   Requires legacy financial-row/action classes during migration. */

.review-item {
  --review-item-bg: var(--surface);
  --review-item-border: var(--border);
  --review-item-text: var(--text);
  --review-item-muted: var(--muted);
}

.review-item--state-needs-review {}
.review-item--state-ready-to-confirm {}
.review-item--state-suggested {}
.review-item--state-possible-duplicate {}
.review-item--state-duplicate {}
.review-item--state-confirmed {}
.review-item--state-matched {}
.review-item--state-ignored {}
.review-item--state-failed {}

.review-item__main {}
.review-item__topline {}
.review-item__meta {}
.review-item__date {}
.review-item__amount {}
.review-item__description {}
.review-item__status {}
.review-item__signals {}
.review-item__actions {}
.review-item__ledger-summary {}
.review-item__panels {}

@media (max-width: 760px) {
  .review-item {}
}
```

Import strategy later:

1. Add the module after current legacy review CSS import/order in whatever CSS
   loading mechanism the project chooses.
2. Style only new aliases first.
3. Compare screenshots.
4. Move declarations out of `app.css` in small chunks.

## Visual Regression Baseline

Before any production CSS change:

1. Create or identify fixture data for all visual states:
   `needs_review`, `ready_to_confirm`, `suggested`, `possible_duplicate`,
   `duplicate`, `confirmed`, `matched`, `ignored`, `failed`.
2. Include variants:
   - income, expense, transfer money tone;
   - no panels vs panels;
   - category panel open;
   - transfer panel open;
   - lazy panel placeholder;
   - action error;
   - category dialog open/error;
   - OOB replacement after action;
   - mobile viewport.
3. Capture desktop baseline at a review page width around 1280px.
4. Capture narrow/mobile baseline around 390px.
5. Include one target/hash state and one working state after HTMX action.
6. Compare:
   - root dimensions;
   - amount/date alignment;
   - action wrapping;
   - panel tab visibility;
   - drawer width and margin;
   - problem/warning/danger contrast;
   - scroll position after HTMX replacement.

Suggested manual smoke checklist:

- click primary confirm on a confirmable row;
- open category panel, submit with missing/invalid data if possible;
- open transfer panel and switch match modes;
- mark possible duplicate as unique;
- restore ignored row;
- undo posted confirmed/matched row;
- reload page with `#raw-transaction-*` anchor.

## Small Commit Plan

Commit 1: document and fixtures

- add this migration plan;
- add or document fixture path/state coverage if test fixtures already exist;
- no runtime code changes.

Commit 2: template aliases only

- add `data-state`, `review-item--state-*`, `review-item--is-next`,
  `review-item--has-panels`, `review-item--has-summary`;
- keep all legacy classes;
- update/prepare snapshot or template tests if present;
- no visual CSS changes.

Commit 3: module shell and no-op token aliases

- create `components/review-item.css` with local custom properties and empty or
  behavior-neutral selectors;
- import it after legacy `app.css` review block if the CSS pipeline supports
  modular imports;
- verify no screenshot diff.

Commit 4: move root/status/ledger declarations

- move only root, state border/background, state tokens, signals, and ledger
  summary declarations to new aliases;
- keep legacy declarations as fallback or duplicate during review;
- run screenshots and responsive checks.

Commit 5: move action wrapper and responsive rules

- migrate Review Item wrapper rules around actions, not shared `ui/_action`;
- mirror responsive selectors for new aliases;
- remove only proven duplicate legacy selectors.

Commit 6: panel payload migration

- migrate `review-panel` and panel form CSS after root Review Item is stable;
- remove `!important` only with verified specificity/order replacement.

## Readiness Checklist

Ready to start Commit 2 when:

- every current visual state has a fixture or reachable manual scenario;
- `parse_error` decision is recorded as alias-to-`failed` for current code;
- `normalized` selector is either fixture-proven reachable or marked legacy-only;
- baseline screenshots exist for desktop and mobile;
- the team accepts modifier plus `data-state` transitional contract;
- no shared action partial rename is included in the Review Item pilot.

Ready to delete legacy selectors when:

- old and new classes have coexisted through at least one visual migration;
- Playwright or manual screenshots pass for all states and mobile;
- `import-review-scroll.js` has either moved off `.review-item` safely or the
  class remains permanent by design;
- no non-review template relies on the selector being deleted;
- combined selectors have replacement coverage.

## Unknowns

- Exact automated fixture strategy for creating every review visual state.
- Whether `RawTransactionStatus.EXTRACTED` reaches the review page in current
  production flows.
- Whether `.review-item--status-normalized` is dead CSS or protects a rare
  path.
- Whether the project wants `review-item--state-*` classes generated in the
  presenter instead of using Jinja `replace`.
- Whether future theme support should promote component aliases to global
  semantic tokens after one or two migrated components.
