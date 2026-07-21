# React Form Design

Status: active child specification of
[`DESIGN.md`](DESIGN.md) and
[`REACT_FRONTEND_DESIGN.md`](REACT_FRONTEND_DESIGN.md).

## Goal

Forms must be easy to scan, keyboard-accessible, themeable and predictable
across features. We reuse stable form semantics and geometry while keeping
entity fields and workflows explicit in feature code.

The reference implementation is the React manual ledger.

## Composition Boundary

```text
native input/select/textarea/radio
  -> Field or Fieldset
  -> FormSection / FormGrid / FormActions / FormErrorSummary
  -> feature draft and feature-specific fields
  -> contextual owner: row expansion, inline toolbar or WorkbenchPanel
  -> API request mapper
```

Shared UI owns:

- label, hint and inline-error placement;
- semantic grouping with `fieldset` and `legend`;
- section, responsive grid and footer geometry;
- a linked error summary;
- focus and theme-visible states.

Feature code owns:

- field names, options and conditional fields;
- draft type and state transitions;
- business wording and validation mapping;
- request construction, retry and success behavior.

Do not build a schema-driven universal form. Similar fields are not enough to
prove that two workflows have the same contract.

## Entity And Operation Forms

Read creation and edit forms in this order:

```text
meaning         operation type
money           account(s) / amount / date
classification category / property
details         description
actions         primary submit / quiet cancel
```

- Prefer one compact reading flow. Add visible sections only when they clarify
  genuinely complex groups; do not repeat field meaning in headings and hints.
- Choose the form container from the task context. Manual-ledger creation opens
  in a right-side `WorkbenchPanel`, because it creates a new entity and does not
  belong to an existing row. Editing expands the selected operation row,
  because the user must see exactly which financial record is being corrected.
- Use radio buttons when there are a few important mutually exclusive choices.
- Do not preselect a financially meaningful choice merely for convenience. For
  example, creation starts without an operation type so that income cannot be
  recorded accidentally when the user intended an expense.
- Use a select for a longer reference list.
- Show the currency next to the amount as soon as its account is known. Never
  make the user infer a money unit from context.
- Hint text must resolve a likely ambiguity. Do not write `Необязательное поле`
  under every optional control when the empty option already communicates it.
- Keep short related values in columns, but preserve the same DOM and reading
  order at every viewport.
- Give free text enough width; use a textarea for descriptions that can grow.
- Group conditional fields by meaning. A transfer shows source and destination
  accounts and does not show income/expense classification fields.
- Keep the primary action explicit: `Создать доход`, not `OK` or `Сохранить`.

## Filter Forms

Filters are secondary list tools and use a separate behavior contract:

```text
toolbar         persistent search / filter disclosure / create action
summary         active count and readable applied values
common          period / status
advanced        type / account / category / property
actions         apply / reset
footer          result range / page size / pagination
```

The controls edit a local draft. `Применить` copies normalized values to the
URL, resets the page to one and triggers list loading. The URL is the applied
state. Do not submit a select immediately on change.

Route navigation announces its pending state and temporarily disables controls
that could start a second conflicting navigation. Search remains visible even
when structured filters are collapsed.

Page size belongs next to the list because it changes presentation density,
not which entities match.

Keep the open filter panel toolbar-like: common controls form a compact grid,
advanced classification stays in one disclosure, and explanatory prose is
omitted when labels are self-sufficient.

The page uses one bordered workbench rather than unrelated full-width sections.
Its header, toolbar, expandable filters, operation collection and pagination
footer share one visual boundary. Filters expand directly below the toolbar;
their position and reading order remain the same on desktop and mobile.
The operation collection is a flat, divider-separated list inside this
boundary. Individual operation rows are not nested cards.

## Manual Ledger Workbench

The workbench has three deliberately different interaction scopes:

- **Collection scope:** search, filters, result count, page size and pagination
  belong to the workbench, because they affect the entire collection.
- **New entity scope:** creation uses `WorkbenchPanel`. It keeps the collection
  visible without pretending that a new operation belongs to a current row.
- **Existing entity scope:** editing expands only the selected row. The row
  keeps its date, money, description and right action area visible above the
  form; only one row can be edited at a time.

The DOM order does not change by viewport. Desktop uses available width for
compact columns; mobile collapses the same toolbar, rows and footer vertically.
Closing an editor returns focus to its `Исправить` button. While an edit is
active, collection navigation and creation are disabled so that the edited
record cannot silently leave the page.

The composition borrows the collection toolbar and expandable-row ideas from
Carbon Data Table, in-context row actions from Cloudscape, and filter/pagination
placement from Shopify Polaris. We reuse the interaction model, not Carbon's
table markup:

- <https://carbondesignsystem.com/components/data-table/usage/>
- <https://cloudscape.design/patterns/general/selection/>
- <https://polaris-react.shopify.com/components/tables/index-table>

## Accessibility And Validation

- Every native control has a visible label and stable `id` and `name`.
- Related radios use `fieldset` and `legend`.
- Required state is visible and also expressed by native HTML where applicable.
- Invalid controls use `aria-invalid` and connect to inline errors with
  `aria-describedby`.
- Failed submission renders an announced summary. Each known field error links
  to its control; the same specific message remains next to the field.
- After server validation, focus moves to the first invalid control.
- DOM order always matches visual and keyboard order.
- Controls retain the project minimum touch height and visible focus ring.

## State And Dependencies

Use controlled React fields: `value` or `checked` comes from the draft and
`onChange` creates the next draft. Keep this state in the closest form feature.

Do not add a form framework by default. Reconsider one only when several real
forms demonstrate repeated nested validation, dynamic collections or measurable
render/performance problems that the small foundation cannot address clearly.

## CSS Rules

- Form components use semantic design tokens; raw palette values stay in theme
  files.
- Shared CSS owns repeated geometry. Feature CSS owns entity-specific choices
  and local composition.
- Responsive grids collapse without CSS reordering.
- A new theme must not require duplicating form layout rules.

## Review Checklist

- Can the form be understood by reading its TSX top to bottom?
- Are primary, classification and supporting data visually distinct?
- Is every label, error and group meaningful without relying on placeholder
  text?
- Does keyboard focus reach controls and return sensibly after closing panels?
- Are applied filters visible without reopening the filter panel?
- Is repeated code a stable UI responsibility, or merely similar feature code?
