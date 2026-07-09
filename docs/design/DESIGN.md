# DESIGN.md - Booker Tee UI/UX Principles

UI/UX direction for Booker Tee.

Status: active design reference.

Read when changing layout, templates, CSS, actions, empty states, status badges,
financial rows, or user flows.

Do not use as the detailed implementation plan for the current import review
refactor. For that, read
[`REFACTOR_PROJECT_DESIGN.md`](REFACTOR_PROJECT_DESIGN.md). If the two documents
conflict on the first import review slice, `REFACTOR_PROJECT_DESIGN.md` has
priority.

Current assessment: the first UI cleanup phase is mostly complete. The design
work is no longer about adding more boxes, hints, and buttons. The next phase is
about clarity, reuse, financial hierarchy, and a calmer modern style.

---

## 1. Interface Goal

Booker Tee should feel like a reliable financial workbench:

```text
understand context
-> import or enter data
-> review uncertainty
-> confirm financial meaning
-> see results
-> tune rules and reference data
```

The interface should help the user avoid mistakes with workspace, account,
income, expense, transfer, category, property, and review status.

---

## 2. Visual Direction

Booker Tee should feel like a modern financial workbench:

```text
calm
dense
precise
private
functional
trustworthy
distinctive
```

The style may keep restrained rebellious creativity:

```text
sharp enough to feel personal and memorable
quiet enough to never compete with money, statuses, and decisions
```

Keep:

- dark-first interface;
- strong readability;
- clear financial hierarchy;
- compact data density;
- confident accent colors;
- expressive but consistent badges;
- subtle interaction feedback;
- a little personality in copy, rhythm, and details.

Avoid:

- decorative brutality;
- visual aggression;
- sterile generic SaaS sameness;
- excessive borders and nested boxes;
- playful/gamified finance;
- style choices that make reports or review slower to scan.

The old `techno-neobrutalist` direction is not a hard requirement anymore.
Booker Tee can keep its character without forcing every screen into harsh
rectangles, terminal mood, or high-friction visual density.

Style changes should happen through shared components and CSS tokens, not by
redesigning every page separately.

---

## 3. Core Principles

1. Financial clarity is more important than decoration.
2. The current user and workspace must be visible in the main app shell.
3. Main workflows must be understandable without reading documentation.
4. Similar entities should look and behave similarly across pages.
5. Statuses, operation types, money direction, and dangerous actions need one
   visual language.
6. Tables are useful only when they improve scanning. Complex rows may use
   compact cards instead.
7. Empty states should explain what is missing and point to the next useful
   action.
8. Technical details should be available, but not visually equal to financial
   decisions.
9. One screen should have one main next step.
10. Reuse components and patterns before inventing another local variant.

---

## 4. App Shell And Navigation

The top-level layout should separate:

- context: current user and workspace;
- main work: dashboard, accounts, operations, imports, reports;
- reference data: categories, properties, rules;
- system/admin: users, workspaces, integrations.

Primary global action:

```text
Загрузить выписку
```

On any authenticated page, the user should understand:

```text
I am working as <user>
inside workspace <workspace>
```

---

## 5. Money First

The main object of Booker Tee is money.

Financial screens should first show:

- current money position;
- income;
- expenses;
- profit/result;
- rows requiring a decision;
- what will change after confirmation.

Principle:

```text
money first
decision second
technical details last
```

Suggested reusable classes:

```text
money-value
money-income
money-expense
money-transfer
money-profit
kpi-strip
money-card
```

Rules:

- amounts should be easy to scan;
- currency must stay near the amount;
- negative values must not disappear in normal text;
- financial values should usually be more visually important than UUIDs,
  timestamps, parser names, and debug state.

---

## 6. Financial Row Pattern

For review rows, manual operations, account movements, and similar lists, use a
common pattern:

```text
Date                                      Amount
Description
Human meta: category, account, calm status
Important signals only when action is needed
Actions / drawer / technical details secondary or collapsed
```

This pattern should feel familiar across:

- import review;
- manual operations;
- account detail;
- reports;
- transaction rules where applicable.

Do not force one universal component for every entity. Reuse the pattern and
shared partials where the UX concept is actually the same.

Base type scale:

```text
date:        financial-row__date        1.4rem
amount:      financial-row__amount      1.4rem
description: financial-row__description 1.02rem / 680
meta:        financial-row__meta        compact, secondary
```

Normal statuses are calm metadata, not primary badges:

```text
confirmed / posted / imported / from statement
```

Important statuses and problems become visible signals:

```text
needs review / error / duplicate? / unrecognized / missing category
```

Financial row meta chips have a semantic order. They are not arbitrary tags.
The first chip should answer what the operation means.

For income and expense rows:

```text
category -> property/object if present -> account/context -> status
```

Examples:

```text
Продукты -> Экспобанк карта -> подтверждено
Прочий доход -> Наличка -> подтверждено
Без категории -> Экспобанк карта -> нужна проверка
```

For transfer rows:

```text
source account -> destination account -> impact/context if useful -> status
```

Examples:

```text
ВТБ вклад -> Экспобанк карта -> не влияет на прибыль -> подтверждено
ВТБ вклад -> Экспобанк карта -> Экспобанк карта -> не влияет на прибыль -> подтверждено
```

The account/context chip may appear on account detail pages because the user is
viewing a single account timeline. It should not be added just to repeat the
route on a generic list.

Status placement:

- calm statuses such as `подтверждено` are last and visually secondary;
- important statuses and repair problems may also appear as top-row signals;
- `доход`, `расход`, and `перевод` should not be repeated in meta chips when
  the row tone, amount direction, category, or transfer route already makes the
  operation type clear.

### Row Actions And Drawers

Financial rows may have an action rail and a row-level drawer.

Action rail rules:

```text
primary action
secondary action
technical details collapsed
```

- Primary action opens or performs the most useful row action.
- Secondary actions link to source/context, for example import row.
- Technical identifiers stay collapsed.
- Do not duplicate the same secondary action inside the drawer if it already
  exists in the action rail.

Drawer rules:

```text
drawer header: short action title and context
drawer body: compact fields
drawer footer: final submit action, aligned right
```

Drawers should feel like an extension of the row, not a separate page nested
inside the row. Use a compact shared structure:

```text
row-actions
row-actions__primary / row-actions__secondary / row-actions__technical
row-drawer
row-drawer__header / row-drawer__form / row-drawer__footer
```

Use row-level drawers for transaction repair, review panels, and compact
row-specific decisions. Do not style a row drawer as a full page form nested
inside a card.

Drawer toggle buttons keep their action label while the drawer is open. For
example, `Исправить` should stay `Исправить`; it should not turn into a green
`Закрыть`. Closing is the behavior of the drawer/accordion itself, while the
drawer footer should contain only the data-changing submit action.

`action-details`, `action-accordion`, and `form-panel-embedded` are still valid
for page-level collapsible tools, filters, creation forms, and technical
details. They should not be introduced for row-level transaction repair when
`row-actions` / `row-drawer` can express the same interaction.

Accepted row-level language:

```text
Исправить        opens a row repair drawer/panel
Открыть операцию links to the operation screen
строка импорта   links back to the source import row
Еще действия     reveals secondary and dangerous actions
```

### Entity Work Row Contract

The financial row pattern has grown into a broader entity row/card language.
Use it for dense working lists of important entities, not only money
movements. Good candidates include transaction rules, account movements,
manual operations, import review items, categories, properties, and similar
reference entities.

Default geometry:

```text
left:  entity meaning, facts, status/result signals
right: actions
below: full-width drawer/form when editing or resolving the entity
```

Rules:

1. The left side owns information: title, human description, route/meaning,
   calm metadata, and compact status/result signals.
2. The right side owns actions only. It should not become a save panel, a
   duplicate status area, or a second data summary.
3. The two zones should be separated by the same calm vertical divider rhythm
   used by `financial-row__side`.
4. Compact status/result anchors may live in the left side's right edge, like
   an amount or `активно` badge. They are still information, not row actions.
5. A row/card has one visible primary action. Secondary actions are visually
   calmer. Rare actions go to `Еще действия`.
6. `Еще действия` is an explicit text action, not an ellipsis icon. Its shape
   should match the import review action menu language.
7. Dangerous actions live inside the additional-actions/danger zone and require
   confirmation when destructive. They should not sit next to save/edit/apply
   actions as equal buttons.
8. Editing opens a row drawer/panel under the row/card. The drawer spans the
   full row/card width, has the same drawer header/body/footer rhythm, and keeps
   the submit action inside the drawer footer.
9. Opening the drawer should not replace the right-side action rail with a
   different set of buttons. The action rail stays stable; the form owns save.
10. Technical details, IDs, debug payloads, and rare administrative controls
    stay collapsed or visually secondary.

Implementation guidance:

```text
financial-row / entity-card root
financial-row__main         left information zone
financial-row__side         right action zone
row-actions                 primary/secondary/more action rail
row-drawer                  full-width edit/resolve drawer
operation-form / feature form classes
ui/_action.html + ActionVM  shared action shape
```

This is a design contract, not a command to extract a universal Jinja partial.
Prefer feature-owned templates that reuse the same CSS/action language. Extract
a shared partial only after the same markup and behavior have stabilized across
several screens.

### Entity Feedback And Local Update Contract

Entity/reference screens should preserve the user's working context after a
row-level action. A save, toggle, restore, cancel, or similar action should not
send the user to the top of the page or make the screen jump when the result can
be represented by updating the affected row.

Default behavior:

```text
HTMX request     -> replace the affected row/card in place
non-HTMX request -> redirect fallback to the affected entity anchor
```

Use local HTMX updates for actions that only change:

- the current row/card;
- a small page summary or queue counter that can be updated out-of-band;
- sibling rows directly affected by the same workflow.

Use full-page redirects for actions that change the page context, route,
workspace, filters, pagination, or a broad list state that has not yet been
given a stable partial/OOB contract.

Feedback and highlighting semantics:

1. Persistent color belongs to meaning: money direction, problem/error states,
   danger, or an explicit current workflow item.
2. Calm statuses such as `активно`, `подтверждено`, or `импортировано` should be
   readable but not compete with primary content.
3. `:target` is navigation focus and fallback only. It should be subtle and
   should not look like a permanent status or problem.
4. "Just changed" feedback should be short-lived and calm. Prefer HTMX settling
   or a temporary client-side state over a permanent ViewModel flag.
5. Row update swaps should avoid automatic scrolling unless the action's purpose
   is navigation. Use the import review pattern as the reference:

```html
hx-boost="true"
hx-select="#row-id"
hx-target="#row-id"
hx-swap="outerHTML show:none"
hx-push-url="false"
```

Do not move HTMX metadata into the shared `ActionVM` until repeated screens prove
that action-level HTMX is the stable abstraction. It is acceptable, and often
cleaner, for the row/card root to own the local update behavior while the actions
inside continue to use the shared `ui/_action.html` shape.

### Created Entity Feedback Pattern

When a user creates an entity inside a long reference/entity list, the UI should
make the result easy to find without changing the whole list's sorting or
scrolling unexpectedly.

Use this pattern for transaction rules, categories, properties/objects, and
similar reference data screens when the list can grow enough that a newly created
item is not immediately visible.

Default shape:

```text
short feedback above the list:
  entity ready
  human title
  identifying condition / meaning
  [Show in list]

the created row:
  calm recent-highlight
```

Rules:

1. Do not reorder the whole list just to bring the new entity to the top.
2. Do not force-scroll the page after creation. Let the user choose `Show in
   list` when they want to jump to the row.
3. Keep the feedback compact. It confirms the result; it is not a second card
   editor.
4. Use calm accent feedback, not a permanent green success state.
5. Presenter/ViewModel prepares `recent_entity` / `recent_entity_id` state.
   Templates only render that state.
6. The list partial owns the feedback block and the row highlight.
7. The link should target the created entity's stable anchor.
8. HTMX create responses should pass the recent entity id into the list partial.
   Non-HTMX fallback may still redirect to the entity anchor.

### Financial Forms

Creation and repair forms should share a calm, predictable structure without
forcing every form into one Jinja macro too early.

Use these form families:

```text
operation-form  creates or repairs a financial operation
filter-form     narrows a list of operations or movements
account-tool-form / entity-tool-form
                changes the entity itself, not a movement
row-drawer      hosts row-level repair forms under a financial row
```

`operation-form` fields should usually read in this order:

```text
primary:        type / amount / date
classification: account(s) / category / property
footer:         description and submit action
```

For imported operations where type/date/amount are not editable in the current
flow, keep the same visual skeleton and only show the editable subset:

```text
primary:        description / status
classification: category / property
footer:         submit action
```

Do not build a universal operation form partial until the repeated shape is
stable across at least a few screens. Prefer shared CSS classes and explicit
feature-owned templates first.

`filter-form` is a secondary tool, not the main content of the page. It should
stay compact:

```text
summary: filters title / applied state / open-close control
hint:    one small line, not a large notice panel
fields:  period / search / status first, then exact classification filters
footer:  compact reset and apply actions
```

When filters are not active, keep the filter block collapsed by default. When
filters are active, show that state in the summary and open the block where it
helps the user understand the current list.

### Financial Row Modes

Use one financial row geometry with different modes, not a new geometry for
each screen.

```text
Financial row
-> review mode: user decides what an uncertain row should become
-> ledger mode: user understands what already happened on an account
-> manual-edit mode: user creates or corrects a manual operation
```

The base geometry stays stable:

```text
date                                  amount
description
financial meaning: category, property, accounts, calm status
important signals only when action is needed
secondary details collapsed
technical details hidden
```

The action area may change by mode, but its position and hierarchy should not:

- review rows emphasize the decision: confirm, change, transfer, ignore;
- account ledger rows emphasize the result and safe correction: summary,
  edit/source/more actions;
- manual operation rows emphasize editable fields and lifecycle actions.

For account detail, do not invent a separate timeline geometry just because the
screen is historical rather than review-oriented. It should render ledger
movements using the same financial row rhythm as import review:

```text
date                                      amount
description
category/property or transfer route/account/calm status
```

The right side of an account movement row should be a compact result/action
zone, not a heavy nested operation card. Editing should open a row-level drawer
under the movement, across the row width, so forms have enough room and do not
compete with the action column.

---

## 6.1 Visual Geometry Contract

Different pages may have different jobs, but they should not surprise the user
with a different information geometry.

When refactoring an existing workflow, first identify the nearest reference
screen and follow its layout rhythm:

- page context on the left, page actions on the right;
- money/date/status in stable positions across related rows;
- primary action visually stronger than secondary actions;
- dangerous actions separated from normal actions;
- technical details collapsed and visually secondary;
- repeated entities use the same density, border radius, badge language, and
  action placement unless the workflow genuinely requires a different shape.

For the imports flow, the current visual reference is the stabilized
`import/review` screen. Document detail, mapping, upload result, and import list
pages should move toward the same geometry:

```text
context / status / financial facts        actions / next step
main content rows                         secondary details collapsed
```

A page may intentionally differ from `import/review`, but the reason should be
explicit:

- it has no row-level decisions;
- it is a setup/configuration screen rather than a review screen;
- it is a report optimized for comparison;
- it uses a shared app-level component with an established shape.

Local visual improvements are not enough if they create a third or fourth
layout language inside the same workflow.

## 6.2 Working Screen Contract

For financial workbench screens, reuse the same behavioral contract before
inventing a new local layout.

Default screen structure:

```text
page context / facts                 page actions / next step
main data or rows                    secondary tools collapsed
technical details                    hidden or clearly secondary
```

Rules:

1. The main screen shows data and decisions first, not a large form.
2. Forms appear as actions: row drawer, compact accordion, modal, or a dedicated
   edit/detail page.
3. A screen or row has one primary action in the active context.
4. Secondary actions stay calm and predictable.
5. Dangerous actions are separated from save/edit/apply actions.
6. Filters are secondary tools: compact, collapsible when inactive, and able to
   summarize active conditions.
7. Technical details are available for people who need them, but hidden from the
   normal reading path.
8. Similar financial rows keep the same order:

   ```text
   date + amount
   description
   category / transfer route / account context / calm status
   ```

9. Normal statuses are quiet metadata. Problem statuses and required decisions
   get visual emphasis.
10. Reuse the existing `financial-row`, `row-actions`, `row-drawer`,
    `operation-form`, and `filter-form` language where it fits. Prefer
    feature-owned templates with shared classes before extracting a universal
    macro or partial.
11. Entity/reference screens should start from the Entity Work Row Contract
    before inventing a local card shape, action menu, or edit form layout.

This contract is intentionally smaller than a full design system. It is a
review checklist for new or refactored screens: if a page breaks the contract,
the reason should be deliberate and visible in the implementation.

---

## 7. Status And Badge Language

Use one semantic language for statuses and operation types:

```text
income        -> green
expense       -> red/pink
transfer      -> blue/neutral
warning       -> yellow
confirmed     -> calm green
needs_review  -> yellow
ignored       -> muted
archived      -> muted
error         -> red
```

Reusable classes:

```text
badge
badge-income
badge-expense
badge-transfer
badge-warning
badge-muted
badge-danger
```

Do not create a new status style on each page.

---

## 8. Action Hierarchy

Too many equal buttons reduce confidence.

For rows/cards with many actions:

```text
1 primary action
0-1 visible secondary action
rest in "Еще" / action menu
danger actions separated
```

Rules:

1. A row/card should answer: "What should I probably do now?"
2. Secondary actions must not compete with primary.
3. Rare actions go to `details`, `Еще`, or an action menu.
4. Dangerous actions are visually separated and require confirmation when
   destructive.
5. The action set depends on entity state.
6. Confirmed entities should show result and focused correction/open actions,
   not the full unresolved form again.
7. `Еще действия` should use the shared text-button/menu rhythm. Avoid local
   ellipsis-only controls or one-off icon menus for the same concept.

For import review, the detailed action policy lives in
[`REFACTOR_PROJECT_DESIGN.md`](REFACTOR_PROJECT_DESIGN.md).

Reusable classes:

```text
primary-action
secondary-actions
action-menu
danger-zone
ui-action__form
ui-action__button
ui-action__label
```

Shared action VM contract:

```text
app.shared.ui.actions.ActionVM
```

Feature presenters decide which actions exist. The shared action contract only
standardizes how actions are described for templates: id, label, icon,
placement, action type, target URL/form/panel, style, hidden fields, and confirm
message.

---

## 9. Forms And Editing

Rules:

1. Creating a simple entity may use a compact form at the top of the page.
2. Editing a simple entity may be inline or on a detail page, depending on
   density.
3. Editing a complex entity should use a dedicated detail/edit surface.
4. Forms should be dense but readable.
5. Fields should group by meaning, not by database order.
6. Dangerous actions should not sit inside the same visual rhythm as save
   actions.
7. After an action, the user should stay in the working context.
8. Row/card edit forms should use the same drawer rhythm where possible:
   header with short title and context, compact grouped body, and submit action
   in the footer. A drawer edits the full entity and should span the full
   row/card width.

Suggested reusable classes:

```text
form-panel
form-grid
form-actions
entity-card
entity-row
```

---

## 10. Technical Details

Technical details are useful for development and debugging, but they should not
compete with money and user decisions.

Hide by default:

- full UUIDs;
- storage keys;
- raw tables;
- raw text;
- parse attempt debug;
- dedupe/debug fields;
- long parser messages;
- raw JSON.

Keep visible:

- account;
- amount;
- date;
- category;
- property;
- review state;
- clear operation description;
- linked operation summary.

Reusable class:

```text
technical-details
```

---

## 11. Icons And Compact Actions

Icons are useful when they save space and the meaning is familiar.

Rules:

```text
primary actions -> text button
frequent secondary actions -> icon button + title/aria-label
danger actions -> text or icon+text with danger style
rare actions -> "Еще" / action menu
```

Every icon-only button must have:

- `aria-label`;
- `title`;
- stable touch target, at least 44x44px;
- one consistent icon style.

Reusable classes:

```text
icon-button
icon-button-danger
icon-button-muted
sr-only
```

---

## 12. Density And Space

Booker Tee is a working financial tool. Screens should be compact and
scannable.

Prefer:

```text
repeated rows -> compact rows/cards or table
simple entity -> compact form or inline edit
complex entity -> detail/edit page
metadata -> small chips/badges
main action -> visible, not huge
```

Avoid:

- large hero blocks inside working sections;
- cards inside cards;
- long explanatory text where a clear label is enough;
- unnecessary horizontal scroll;
- huge forms where every field takes a full row;
- decorative empty space that pushes useful data below the first screen;
- mobile screens that feel like stacked nested boxes.

A good screen answers:

```text
where am I?
what matters now?
what requires action?
what is the next step?
```

---

## 13. Empty States And Hints

Empty states should explain the current absence of data and offer the next
useful action.

Guidance:

- one page should not show multiple competing CTAs for the same action;
- `next_step`, `inline_hint`, `notice`, `empty_state`, and `workflow_steps`
  should have distinct roles;
- do not show an empty-state CTA if the creation form is already visible;
- `next_step` should appear only when it truly advances the current workflow.

---

## 14. Core User Paths

First setup:

```text
create user
-> create/select workspace
-> create account
-> upload statement
-> review transactions
-> open report
```

Regular work:

```text
select workspace
-> upload statement
-> apply suggestions/rules
-> review rows
-> confirm operations
-> inspect reports
```

Reference setup:

```text
accounts
-> categories
-> properties
-> rules
```

---

## 15. Refactor Priority

Current priority is not a visual redesign for its own sake.

Refactor in this order:

1. Import review item and action system via ViewModel/Presenter.
2. Account detail financial rows.
3. Manual operations.
4. Shared CRUD/reference screens: categories, properties, users, workspaces,
   rules.
5. Reports and financial summaries.
6. Mapping and unknown statement flows.

Use shared components where concepts are stable:

```text
badge
money-value
entity-card
form-panel
action-menu
technical-details
empty-state
```

---

## 16. UI Audit

For browser checks, use Playwright audit scripts:

```bash
uv run python scripts/ui_audit.py
uv run python scripts/ui_audit.py --authenticated
uv run python scripts/ui_audit.py --scenario realistic
uv run python scripts/ui_audit.py --scenario review_interactions
uv run python scripts/ui_audit.py --scenario design_audit
```

Use `--base-url` when the app is already running:

```bash
uv run python scripts/ui_audit.py --base-url http://127.0.0.1:8000 --scenario realistic
```

For everyday UI refactor checks, prefer `--scenario realistic`. It creates real
financial/import data and checks desktop/mobile core pages without the expensive
full button-click sweep. Reserve `button_audit` for deliberate action-system
changes or a final broader pass; it is intentionally slow.

Minimum checks:

- no HTTP 500/404 on key pages;
- no console/page errors;
- no failed requests;
- no unintended horizontal overflow;
- desktop and mobile screenshots are readable;
- critical HTMX interactions work;
- design audit does not reveal button noise, visible debug data, broken badges,
  or nested-box overload on core screens.

`design_audit` may fail with findings. Treat it as a design reviewer, not only a
CI smoke test.

---

## 17. Progress Snapshot

Already achieved:

- app shell with user/workspace context and primary action;
- dashboard shell;
- baseline shared `badge`, `entity-card`, `form-panel`, empty states;
- common visual language applied to accounts, rules, manual operations, imports,
  categories, properties, users, and workspaces;
- import review made denser and more review-focused without changing business
  logic;
- `ReviewItemVM`-based import review slice stabilized; active review rendering
  no longer uses the legacy `RawTransaction` partial fallback;
- document detail and unknown mapping pages moved to presenter/ViewModel-backed
  template contracts;
- imports flow pages started moving toward one shared review-inspired geometry:
  page context, next step, primary action, technical details last;
- new and touched imports controls are migrating toward BEM-like naming by
  owner, for example `site-header__*` and `mapping-table-picker__*`;
- technical/debug details hidden more consistently;
- Playwright `ui_audit`, `button_audit`, and `design_audit` added;
- current design audit findings for categories and mobile import review cleaned
  up.

Still active:

- Stronger shared action policy and component partials beyond import review.
- Imports flow convergence: keep upload, document detail, mapping, import list,
  and review aligned with the same geometry and action hierarchy.
- Better financial rows for account detail/manual operations/reports.
- Style evolution toward modern financial workbench with restrained rebellious
  creativity.

---

## 18. Not Doing Now

- Marketing landing page.
- Complex onboarding wizard.
- Full RBAC UI redesign.
- Decorative illustrations instead of working financial screens.
- Full visual redesign page by page.
- New frontend framework.
- Style changes that bypass shared components and CSS tokens.
