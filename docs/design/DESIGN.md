# DESIGN.md - Booker Tee UI/UX Principles

UI/UX direction for Booker Tee.

Status: active design reference.

Read when changing layout, components, CSS, actions, empty states, status badges,
financial rows, or user flows.

For the active frontend architecture and migration strategy, read
[`REACT_FRONTEND_DESIGN.md`](REACT_FRONTEND_DESIGN.md). For detailed historical
repeated-row discoveries, also read
[`WORKBENCH_ROW_DESIGN.md`](WORKBENCH_ROW_DESIGN.md). Use
[`FRONTEND_NEXT_DESIGN.md`](FRONTEND_NEXT_DESIGN.md) and
[`REFACTOR_PROJECT_DESIGN.md`](REFACTOR_PROJECT_DESIGN.md) only as a historical
reference for existing SSR behavior and implementation discoveries. If they
conflict with the active React design, `REACT_FRONTEND_DESIGN.md` has priority.

## Роль документа

Этот документ задает пользовательский опыт, визуальную иерархию и устойчивые
interaction-принципы. Он не задает:

- расположение Python, TypeScript, templates и CSS-файлов;
- конкретные имена legacy selectors или partials;
- Python-контракты Presenter/ViewModel;
- порядок миграции workflows;
- активный implementation backlog.

Эти решения принадлежат `REACT_FRONTEND_DESIGN.md`. Названия компонентов в этом
документе обозначают UI-концепты; точный HTML, component props и API contract
определяются рядом с реализацией и не меняют финансовую семантику.

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
8. Internal technical details do not belong to the ordinary user flow.
   Financial traceability is expressed through understandable sources and
   actions, not UUIDs or debug payloads.
9. One screen should have one main next step.
10. Reuse components and patterns before inventing another local variant.

### 3.1 Progressive Disclosure

Booker Tee следует паттерну
**[Progressive disclosure](https://en.wikipedia.org/wiki/Progressive_disclosure)**:
интерфейс сначала показывает информацию и действия, необходимые для текущего
решения, а вторичную сложность раскрывает по запросу пользователя. Это делает
плотные финансовые workflows проще для изучения и снижает вероятность ошибок.

Стандартный порядок раскрытия:

```text
финансовый смысл и текущее состояние
-> основное действие
-> вторичные действия и необязательный контекст
-> форма редактирования/исправления или подробный workflow
```

Progressive disclosure используется для:

- неактивных фильтров и вторичных инструментов страницы;
- редких и опасных действий внутри явной области `Еще действия`;
- lazy edit/repair panels;
- необязательного вспомогательного контекста;
- сложных workflows с безопасной отдельной страницей или панелью.

Нельзя использовать progressive disclosure, чтобы скрывать:

- сумму, валюту, дату или смысл операции;
- ошибки, предупреждения и нерешенное review-состояние;
- последствия финансового действия;
- основное действие, необходимое для продолжения;
- объяснение permissions или readonly-состояния;
- подтверждение destructive action.

Disclosure controls должны оставаться понятными, доступными с клавиатуры и
работать через обычный HTTP fallback. Не использовать глубокую вложенность
accordions и menus: если вторичная область превращается в полноценный workflow,
ей нужна понятная отдельная панель или страница.

---

## 4. App Shell And Navigation

The top-level layout should separate:

- context: current user and workspace;
- main work: dashboard, accounts, operations, imports, reports;
- reference data: categories, properties, rules;
- system/admin: users, workspaces, integrations.

On desktop, global context and navigation live in one persistent left sidebar:

```text
brand
current workspace
grouped work / analysis / reference navigation
current user and role
```

Workspace and user context must not consume a separate row above every working
screen. The workspace card links to workspace management; the user card links
to profile. Do not show a chevron or switcher affordance until an actual
workspace-switching interaction exists.

On mobile, the same hierarchy moves into one keyboard-operable menu. The compact
top bar may repeat only the short workspace name for orientation; the page
content must not duplicate the desktop context header.

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
technical implementation outside the ordinary flow
```

Stable UI concepts:

```text
MoneyValue
KpiStrip
MoneyCard
```

Rules:

- amounts should be easy to scan;
- currency must stay near the amount;
- negative values must not disappear in normal text;
- financial values should usually be more visually important than timestamps
  and processing metadata;
- UUIDs, parser names and debug state are not ordinary page content.

---

## 6. Financial Row Pattern

For review rows, manual operations, account movements, and similar lists, use a
common pattern:

```text
Date                                      Amount
Description
Human meta: category, account, calm status
Important signals only when action is needed
Actions / edit panel secondary until needed
```

This pattern should feel familiar across:

- import review;
- manual operations;
- account detail;
- reports;
- transaction rules where applicable.

Do not force one universal component for every entity. Reuse React components
where the responsibility, UX concept and behavior are actually the same.

Base type scale:

```text
date and amount: visually prominent peers
description:     primary readable text
metadata:        compact secondary text
```

Exact sizes, weights and spacing are defined through foundation tokens, not
hard-coded as a page-specific contract here.

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
rare actions disclosed on demand
```

- Primary action opens or performs the most useful row action.
- Secondary actions link to source/context, for example import row.
- Technical identifiers are not rendered as ordinary row content.
- Do not duplicate the same secondary action inside the drawer if it already
  exists in the action rail.

Drawer rules:

```text
drawer header: short action title and context
drawer body: compact fields
drawer footer: final submit action, aligned right
```

Drawers should feel like an extension of the row, not a separate page nested
inside the row. Use the shared concepts:

```text
WorkbenchRow
ActionStack
ExpansionPanel
```

Use row-level drawers for transaction repair, review panels, and compact
row-specific decisions. Do not style a row drawer as a full page form nested
inside a card.

Drawer toggle buttons keep their action label while the drawer is open. For
example, `Исправить` should stay `Исправить`; it should not turn into a green
`Закрыть`. Closing is the behavior of the drawer/accordion itself, while the
drawer footer should contain only the data-changing submit action.

Page-level disclosure remains valid for filters, creation forms and optional
tools. Row-level repair uses the Workbench Row expansion contract instead of a
separate local accordion language.

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
3. The two zones should use one calm and consistent divider rhythm.
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
10. Technical details, IDs and debug payloads do not appear in ordinary entity
    cards or `Еще действия`. A proven diagnostic need belongs to a separate
    authorized support/debug surface.

Component guidance:

```text
WorkbenchRow     information, actions and expansion geometry
ActionStack      primary, secondary, more and danger hierarchy
ExpansionPanel   full-width edit/resolve surface
MoneyValue       formatted amount and server-provided financial semantics
```

This is a design contract, not a command to extract a universal component.
Feature components live inside their React feature. Extract shared UI only after
the same responsibility, semantic input and behavior have stabilized across
several workflows.

### Catppuccin Color Contract

The official
[Catppuccin style guide](https://github.com/catppuccin/catppuccin/blob/main/docs/style-guide.md)
and [palette](https://catppuccin.com/palette/) are the source of truth for React
frontend color.

Theme architecture has three explicit layers:

```text
--ctp-*          exact official palette values; never adjusted
--accessible-*   documented legibility overrides for a foreground role
--color-*        semantic component contract
```

Catppuccin surface roles are stable:

```text
Base             main application pane
Mantle / Crust   secondary panes and application shell
Surface0–2       controls and elevated surface elements
Text             body and headline text
Subtext0/1       labels and supporting text
Overlay1         subtle non-essential content
Blue             links, actions and active interactive state
Green/Yellow/Red success, warning and danger
Overlay2 at 25%  browser text selection
Rosewater        text caret
```

Booker Tee may use financial Green, Red, Blue and Mauve as persistent product
semantics. A financial label must still state its meaning; color is
reinforcement, not the only signal.

Official palette values are immutable. If an official Latte foreground does not
meet the required contrast for its actual size and surface, define a narrowly
named `--accessible-*` override and preserve the official `--ctp-*` value.
Normal and small text requires at least 4.5:1. The 3:1 threshold is reserved for
large financial text and non-text UI boundaries.

Do not add white or product-specific colors to the `--ctp-*` namespace.
Derived working, target and recent states must compose existing Catppuccin
semantic colors instead of introducing an undocumented palette.

### Entity Feedback And Local Update Contract

Entity/reference screens should preserve the user's working context after a
row-level action. A save, toggle, restore, cancel, or similar action should not
send the user to the top of the page or make the screen jump when the result can
be represented by updating the affected row.

Target behavior:

```text
local mutation success -> replace or refetch the smallest truthful boundary
route/context change   -> navigate and load the new route state
```

Use local React state/server-state updates for actions that only change:

- the current row/card;
- a small page summary or queue counter that can be updated out-of-band;
- sibling rows directly affected by the same workflow.

Use route navigation or route revalidation for actions that change page context,
workspace, filters, pagination, or a broad list state. Legacy HTMX behavior is a
characterization source, not the target response contract.

### Entity State Language Contract

Booker Tee has many dense entity lists: imported rows, ledger operations,
accounts, rules, categories, properties, users, and workspaces. The interface
must help the user understand which item is current, selected, focused, changed,
or problematic without inventing a new visual treatment per screen.

Use this vocabulary consistently:

```text
current context  the entity that defines where the user is working
active work item the entity currently being reviewed or resolved
working card     the card the user is currently interacting with
selected         an entity chosen by the user for a pending action
focus            keyboard/browser focus
recent           just created and worth surfacing after navigation/filtering
problem          error, warning, duplicate, mismatch, or attention state
status           durable entity state such as active, archived, confirmed
```

Visual semantics:

1. Persistent color belongs to meaning: money direction, problem/error states,
   danger, explicit current context, or an active work item.
2. Calm statuses such as `активно`, `подтверждено`, or `импортировано` should be
   readable but not compete with primary content.
3. Selected/current/focused working entities must not rely on border or glow
   alone. They need a visible surface change, structural separation, or an
   explicit label.
4. Persistent current context should prefer structural clarity first: if an item
   defines where the user is working, separate it from peer items with a heading
   such as `Текущее ...` / `Другие ...`, then use color as reinforcement.
5. Booker Tee uses the Catppuccin Mocha direction for selection states:
   lavender/blue/sapphire surfaces for current/selected context. Green remains
   for success/confirmed meaning, not generic selection.
6. Generic live/enabled states such as `активно`, `текущее`, or `доступно`
   should use calm lavender/blue status treatment, not green success styling.
7. Focus is not selection. Browser/keyboard focus should be an outline/ring and
   should disappear when focus moves.
8. `:target` is navigation focus and fallback only. Use it when a page load or
   URL anchor returns the user to an entity. It should be subtle and should not
   look like a permanent status, problem, or selected entity.
9. `working card` is for the card the user just chose to act on. It should move
   when the user clicks another card action and should not depend on timers.
10. Row update swaps should avoid automatic scrolling unless the action's purpose
    is navigation.
11. A local mutation must not mark the changed row as URL `target`. It should
    preserve or set `working card`; route navigation to an anchor may use
    `target`.

Recommended treatments:

```text
current context
  structure: "Текущее ..." / "Другие ..." or an equivalent page-level grouping
  markup: aria-current when appropriate
  color: prefer labels and grouping over a selected card surface

active work item
  structure: keep near the top of the workflow or queue
  color: selected/work surface can be stronger than passive current context
  behavior: local updates, no page jump

working card
  structure: the card whose action/form the user is interacting with
  color: soft lavender work surface; no timer-based flash
  behavior: one working card per screen; moves when another card is chosen
  avoid: single detail/header cards, current-context cards, and admin/user
  management cards unless there is a true peer list interaction

selected
  structure: explicit selected control, checked state, or selected label
  color: Overlay2 at 25% over the owning workflow surface

target
  structure: visible `Текущая строка` marker and aria-current
  color: Overlay2 at 25% plus an Overlay2 outline
  behavior: navigation destination only; do not rename it to selected

focus
  structure: no layout change
  color: outline/ring only

recent
  structure: compact visible `Недавно` pill near the affected row
  color: Blue pill; do not recolor the whole row or use success Green

problem
  structure: explain what needs attention near the entity
  color: warning/danger tones; this can be stronger than normal status

status
  structure: badge/token in the information zone
  color: calm semantic tone; do not turn every normal status into a highlight
```

Workbench row color channels compose instead of replacing one another:

```text
workflow surface   default / review / problem / settled
semantic rail      warning / danger when the row needs attention
ephemeral overlay  target / working
visible marker     target / working / recent
keyboard focus     focus-visible outline
```

`problem` owns its warning rail even while the row is `working` or `target`.
Temporary state must not replace that rail through CSS source order. `working`
uses a Blue 8% overlay and Blue outline; `target` and anchor navigation use the
official Overlay2 25% selection treatment. `recent` uses only a Blue pill.

For `:target` and URL-anchor return states, preserve the entity's semantic left
edge when it exists. A target highlight may adjust the top/right/bottom border,
surface, or inner ring, but it should not overwrite an income/expense/transfer,
problem, category, property, or workflow-status rail.

Current application:

- Workspaces use `current context`: the current workspace is separated from
  other spaces and uses `aria-current`.
- Import review uses `active work item` / queue semantics for rows the user is
  reviewing, and `working card` when the user acts on a specific row.
- Account detail and manual ledger use `target` only for URL-anchor return
  states. Local row replacement after save/cancel/restore should preserve the
  `working card`.
- Transaction rules, categories, and properties use the same language for
  working/recent/problem states as they continue to evolve.
- Do not add `working card` to workspace current-context cards, category detail
  header cards, or user/admin management cards by default.

The existing import-review local update is a behavior reference, not a template
or HTMX contract to copy. React updates the smallest consistency boundary that
keeps the visible page truthful: the affected row, list or related summaries.
Exact API/state boundaries follow `REACT_FRONTEND_DESIGN.md`.

Lazy row drawer loading:

1. Long entity lists should not render heavy closed edit drawers for every row.
2. If a drawer contains repeated reference selects, account/category/property
   options, or a complex correction form, load the drawer body only when the user
   chooses the edit/correction action.
3. The initial row/card render should contain the information shell, actions,
   and an empty expansion target with a calm loading state.
4. The feature loads focused edit data through its JSON API only when the user
   opens the drawer.
5. After saving, replace the affected row/card and let the drawer close as part
   of the row refresh.

Bounded long reference lists:

1. Search/filter is the first response to a growing reference list.
2. If the visible row count can make the initial payload or browser DOM heavy,
   render a moderate initial slice and provide a calm `Show more` action.
3. Avoid numbered pagination for reference cleanup screens unless the user is
   truly navigating separate pages of results. `Show more` preserves scanning
   flow better than page numbers.
4. The list partial owns the visible count, total filtered count, and next URL.
5. Mutating list-level actions should preserve the active query state when they
   replace the list partial.

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
5. Feature state prepares explicit recent-feedback state. Components only render
   that state.
6. The list component owns the feedback block and row highlight.
7. The link should target the created entity's stable anchor.
8. Successful create response returns the entity identity required to reconcile
   the list.
9. Client-side behavior clears recent feedback on the next meaningful
   interaction. Recent is confirmation, not durable domain state.

### Financial Forms

Creation and repair forms should share a calm, predictable structure without
forcing every form into one universal React component too early.

The detailed React composition, accessibility and filter-state contract lives
in [`FORM_DESIGN.md`](FORM_DESIGN.md).

Use these conceptual form families:

```text
OperationForm   creates or repairs a financial operation
FilterForm      narrows a list of operations or movements
EntityToolForm  changes the entity itself, not a movement
ExpansionPanel  hosts row-level repair forms under a Workbench Row
```

`OperationForm` fields should usually read in this order:

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
stable across at least a few screens. Prefer the shared form foundation and
explicit workflow templates first.

`FilterForm` is a secondary tool, not the main content of the page. It should
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

### Workbench Row Modes

Use one Workbench Row geometry with different modes, not a new geometry for
each screen.

```text
Workbench Row
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
```

### Flat Entity Collection Standard

Manual Ledger establishes the default geometry for dense, actionable entity
collections: one bounded workbench surface containing divider-separated flat
rows. Individual rows do not add another card border, radius or shadow. This
keeps the collection readable as one ledger and leaves emphasis for target,
working and problem states.

Operation meaning remains explicit and quickly scannable:

- `доход`, `расход` and `перевод` always use their semantic colored badges;
- every system and user category uses one shared category tone, never a
  per-category palette;
- transfers show both the `перевод` badge and a compact
  `source account -> destination account` route badge;
- the repeated `Не влияет на прибыль` explanation is omitted because transfer
  semantics already guarantee it.

Row editing expands within the same flat row and spans the workbench width.
Do not add a runtime card/flat switch. Use an individually framed card only
when an entity is genuinely standalone rather than part of a dense collection.

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
- internal technical details absent from the ordinary page;
- repeated entities use the same density, border radius, badge language, and
  action placement unless the workflow genuinely requires a different shape.

For the imports flow, the stabilized legacy `import/review` screen is a source
of observed behavior, not a component implementation to copy. Document detail,
mapping, upload result, and review should converge on the same new geometry:

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
user-facing traceability             available through clear links/actions
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
7. Internal technical details are absent from the ordinary page. User-facing
   traceability uses understandable links to the operation, document or import
   source.
8. Similar financial rows keep the same order:

   ```text
   date + amount
   description
   category / transfer route / account context / calm status
   ```

9. Normal statuses are quiet metadata. Problem statuses and required decisions
   get visual emphasis.
10. Start from `WorkbenchRow`, `ActionStack`, `ExpansionPanel`, `MoneyValue` and
    the shared form foundation where they fit. Keep workflow-specific templates
    explicit before extracting a universal component.
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

Semantic tones:

```text
income
expense
transfer
warning
muted
danger
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

The existing import-review action policy is documented historically in
[`REFACTOR_PROJECT_DESIGN.md`](REFACTOR_PROJECT_DESIGN.md). New implementation
contracts follow `REACT_FRONTEND_DESIGN.md`.

React represents this hierarchy through `ActionStack`. Server capabilities
constrain which actions are allowed; the feature places them into presentation
groups. Components do not recalculate permissions.

Exact API/state contracts live in `REACT_FRONTEND_DESIGN.md` and feature code;
this document owns only the visible hierarchy and interaction intent.

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

Stable UI concepts:

```text
UIField
FormLayout
FormActions
ExpansionPanel
```

---

## 10. Technical Details

Internal technical details are useful for diagnostics but do not belong to the
ordinary user interface.

Do not render as ordinary page content:

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

Keep identifiers in URLs, component keys and API requests where required, but
do not render them as ordinary content. Put diagnostic details in sanitized logs
and development tools.
If a real support workflow later requires them, design a separate authorized
support/debug surface rather than adding a generic technical-details block to
normal pages.

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

Stable UI concepts:

```text
IconButton
VisuallyHidden
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

Current priority is not a visual redesign for its own sake. The active migration
order is defined only in `FRONTEND_NEXT_DESIGN.md` and
`WORKBENCH_ROW_DESIGN.md`; do not duplicate it here.

Use shared components where concepts are stable:

```text
UIButton
UIBadge
UIField
MoneyValue
WorkbenchRow
ActionStack
ExpansionPanel
EmptyState
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
uv run python scripts/ui_audit.py --scenario theme_audit --theme catppuccin-latte
```

Use `--base-url` when the app is already running:

```bash
uv run python scripts/ui_audit.py --base-url http://127.0.0.1:8000 --scenario realistic
```

For everyday UI refactor checks, prefer `--scenario realistic`. It creates real
financial/import data and checks desktop/mobile core pages without the expensive
full button-click sweep. Reserve `button_audit` for deliberate action-system
changes or a final broader pass; it is intentionally slow.

`theme_audit` forces one root palette without adding a production preference
switcher. Combine it with `--path` using a URL or stable page label to capture a
focused cross-viewport theme screenshot set.

Minimum checks:

- no HTTP 500/404 on key pages;
- no console/page errors;
- no failed requests;
- no unintended horizontal overflow;
- desktop and mobile screenshots are readable;
- critical interactions and API requests work;
- design audit does not reveal button noise, visible debug data, broken badges,
  or nested-box overload on core screens.

`design_audit` may fail with findings. Treat it as a design reviewer, not only a
CI smoke test.

---

## 17. Legacy Frontend Snapshot

The existing frontend remains a source of observed behavior, UI audit
infrastructure and lessons learned, but not a source of target CSS, templates or
component contracts. Its detailed implementation history lives in
`REFACTOR_PROJECT_DESIGN.md`.

Useful assets to preserve during migration:

- sanitized realistic data scenarios;
- Playwright `ui_audit`, `button_audit` and `design_audit` scripts;
- proven financial and review behavior;
- accessibility, responsive and local-update discoveries;
- known UX failures that the new frontend must not repeat.

This section is not an active backlog. Active implementation sequencing lives
in `REACT_FRONTEND_DESIGN.md`.

---

## 18. Not Doing Now

- Marketing landing page.
- Complex onboarding wizard.
- Full RBAC UI redesign.
- Decorative illustrations instead of working financial screens.
- Uncoordinated page-by-page redesign outside the vertical migration plan.
- Another frontend framework or parallel permanent authenticated UI.
- Style changes that bypass shared components and CSS tokens.
