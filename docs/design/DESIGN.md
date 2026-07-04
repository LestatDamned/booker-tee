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
[amount] [direction] [date] [status badges]        [actions]
Description
Meta: account, category, property, row/source info
Decision/result summary
Technical details collapsed
```

This pattern should feel familiar across:

- import review;
- manual operations;
- account detail;
- reports;
- transaction rules where applicable.

Do not force one universal component for every entity. Reuse the pattern and
shared partials where the UX concept is actually the same.

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

For import review, the detailed action policy lives in
[`REFACTOR_PROJECT_DESIGN.md`](REFACTOR_PROJECT_DESIGN.md).

Reusable classes:

```text
primary-action
secondary-actions
action-menu
danger-zone
```

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
- technical/debug details hidden more consistently;
- Playwright `ui_audit`, `button_audit`, and `design_audit` added;
- current design audit findings for categories and mobile import review cleaned
  up.

Still active:

- ReviewItemVM-based import review refactor.
- Stronger shared action policy and component partials.
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
