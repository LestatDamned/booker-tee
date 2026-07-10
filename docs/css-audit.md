# CSS Audit - Booker Tee

Status: first-stage audit. No production CSS, templates, or Python code were changed.

Scope:

- Main stylesheet: `src/app/static/css/app.css` (7,578 lines).
- Runtime references checked in `src/app/templates`, `src/app/features`, `src/app/static/js`, and `tests`.
- Vendor JS under `src/app/static/js/vendor` was excluded from selector usage decisions.

## 1. Executive Summary

`app.css` is a single dark-first stylesheet with primitive theme-like variables at `:root`, global element styles, layout primitives, old utility/page classes, and newer BEM-style components in one cascade. It has no explicit comments or section markers, so the real structure is inferred from selector clusters.

Key findings:

- 1,167 parsed CSS rules and 773 unique CSS class selectors were found.
- 32 `!important` declarations were found.
- No CSS IDs were found.
- 55 structural-selector cases were found (`>`, `:not()`, `first-child`, `last-child`, etc.).
- 110 classes have no exact static match outside CSS, but 90 of them match dynamic class prefixes.
- 20 selectors are "probably unused" candidates, not deletion candidates yet.
- Current tokens are mostly Catppuccin Mocha-like primitive aliases (`--bg`, `--surface`, `--green`, `--danger`) rather than project semantic tokens.
- Current production loading is one CSS file in `src/app/templates/base.html:7`, with mtime cache-busting from `src/app/templating.py:260` and `src/app/templating.py:285`.

The safest migration path is vertical: choose one component, freeze its states, introduce semantic tokens around that component, move only that component into a module, then retire replaced legacy selectors in a separate commit.

Recommended first component: `Review Item`, but only after screenshot fixtures for all visual states are prepared.

## 2. Current CSS Architecture

Current loading:

- `src/app/templates/base.html:7` loads `/static/css/app.css?v={{ css_version }}`.
- `src/app/templating.py:260` defines `STATIC_CSS_PATH = Path("src/app/static/css/app.css")`.
- `src/app/templating.py:297` uses file mtime as the cache key.
- No theme attribute is currently rendered on `<html>` or `<body>`.
- No CSS build step is currently visible from the checked files.

Current architecture is effectively:

```text
one physical file
-> root variables and base element rules
-> global layout primitives
-> shared UI primitives
-> feature/page clusters
-> responsive overrides
-> late global notice/error/pre styles
```

This is workable for one dark theme, but fragile for multiple themes because components reference low-level color names directly (`--green`, `--danger`, `--surface-strong`) and page-specific selectors override shared components by order.

## 3. app.css Map

The file has no section comments. This map is inferred from selectors and templates.

| Lines | Logical area | Main selectors/prefixes | Related templates/code | Coupling | Risk | Module candidate |
| --- | --- | --- | --- | --- | --- | --- |
| 1-27 | Current root variables and font stack | `:root`, `--bg`, `--surface`, `--green`, `--danger`, `--review-anchor-offset` | all pages through `base.html` | Very high | High | `settings/primitives.css`, `settings/semantic-tokens.css`, later `themes/default.css` |
| 29-57 | Reset/base elements/icons | `*`, `[x-cloak]`, `html`, `body`, `a`, `.icon` | `base.html`, icon helper in `src/app/templating.py` | High | Medium | `generic/reset.css`, `generic/base.css` |
| 59-241 | App shell and global layout | `.shell`, `.site-header`, `.header-grid`, `.context-*`, `.brand`, `.nav-*`, `.page-frame`, `.panel`, `.eyebrow` | `src/app/templates/base.html` | Very high | High | `layout/app-shell.css`, `layout/page.css` |
| 243-390 | Base typography, account detail header, generic stack/toolbar | `h1`, `p`, `.account-detail-*`, `.health-row`, `.stack`, `.toolbar` | `accounts/detail.html`, dashboard/home pages | High | Medium | split between `generic/base.css`, `layout/page.css`, `pages/accounts.css` |
| 391-813 | Import page shell/list/action menus | `.import-page-*`, `.import-document-*`, `.import-index-*`, `.import-action-details`, `.action-menu` | imports index/detail/mapping/upload templates | High | High | `pages/imports.css`, later shared action menu |
| 814-967 | Buttons, inputs, focus, form panel | `.button`, `.primary-action`, `.button-danger`, `.form-panel`, `.field` | almost all forms | Very high | High | `components/button.css`, `components/form-field.css`, `components/form-panel.css` |
| 968-1647 | Unknown statement mapping/import preview | `.mapping-*`, `.choice-*`, `.import-table-*`, `.form-panel-embedded` | `imports/mapping*.html` | Medium | Medium | `pages/import-mapping.css`, `components/file-upload.css` |
| 1648-2117 | Old reference/entity card layer and technical details | `.category-edit-*`, `.filter-tab*`, `.entity-card*`, `.technical-details`, `.admin-details`, `.debug-details`, `.entity-card-actions` | categories, properties, workspaces, accounts | High | High | `components/entity-card.css`, `components/details.css`, some `legacy/legacy.css` |
| 2118-2481 | Dashboard, onboarding, hints | `.dashboard-*`, `.workspace-section*`, `.quick-*`, `.next-step-*`, `.inline-hint*`, `.onboarding-*` | dashboard, shared components | Medium | Medium | `pages/dashboard.css`, `components/inline-hint.css` |
| 2482-2739 | Workflow/review page support | `.workflow-*`, `.review-page-tools`, `.review-support-*`, `.review-control-*`, `.amount-*` | imports detail/review, components | Medium | Medium | `components/workflow-steps.css`, `pages/import-review.css` |
| 2741-2963 | Lists, empty states, metrics, money | `.entity-list`, `.entity-row`, `.empty-state`, `.summary-grid`, `.metric`, `.money-*` | dashboard/reports/imports/reference pages | High | Medium | `components/empty-state.css`, `components/metric.css`, `components/money.css` |
| 2964-3299 | Row actions, row drawer, operation forms, table scroll | `.row-actions`, `.row-drawer`, `.operation-form`, `.table-scroll`, `.field` | ledger manual, account detail, import review | Very high | High | `components/row-actions.css`, `components/row-drawer.css`, `components/operation-form.css`, `components/table.css` |
| 3302-3425 | Badges, tones, base table | `.badge-*`, `.tone-*`, `.amount-*`, `.table` | all status displays and reports | Very high | High | `components/badge.css`, `components/table.css`, semantic status tokens |
| 3426-3780 | Import document detail/raw rows | `.document-detail-*`, `.parse-*`, `.import-parse-*`, `.raw-transaction-*`, `.import-raw-row*` | `imports/detail/*`, `_raw_transaction_row.html` | Medium | Medium | `pages/import-detail.css`, `components/raw-transaction.css` |
| 3781-4208 | Transaction rules CRUD | `.rule-*`, `.detached-form`, `.row-drawer__loading` | `transaction_rules/*`, presenter models | High | High | `pages/transaction-rules.css`, shared `entity-card` |
| 4209-4891 | Categories, properties, workspaces CRUD | `.property-*`, `.category-*`, `.workspace-*` | categories/properties/workspaces templates and presenters | High | High | `pages/reference-data.css`, `pages/workspaces.css` |
| 4892-5000 | Manual operations and old rule card aliases | `.manual-operation-*`, `.rule-card-inactive`, `.rule-card-main`, `.rule-card-title`, `.rule-status` | ledger manual, transaction rules legacy | Medium | Medium | `pages/manual-operations.css`, legacy aliases |
| 5001-5560 | Review queue, financial row, review item core | `.review-list`, `.review-queue-*`, `.financial-row*`, `.review-item*`, `.ui-signal-list`, `.problem-*` | `imports/review/_item.html`, account/detail/manual rows | Very high | High | `components/financial-row.css`, `components/review-item.css` |
| 5561-6705 | Review panels/actions/dialogs and filter/report controls | `.review-panel*`, `.danger-zone`, `.action-*`, `.filter-*`, `.account-tool-form*`, `.report-*`, `.review-actions*`, `.review-category-dialog*` | import review, reports, account filters | Very high | High | `components/action.css`, `components/review-panel.css`, `components/dialog.css`, `pages/reports.css` |
| 6707-6811 | Account movements and pagination | `.account-movement*`, `.entry-description`, `.badge-source-*`, `.pagination-*` | accounts/detail partials | Medium | Medium | `pages/accounts.css`, `components/pagination.css` |
| 6813-7550 | Responsive overrides | four `@media` blocks: 920, 900, 720, 560 | all SSR templates | Very high | High | split near modules after migration |
| 7551-7578 | Late notice/error/pre global rules | `.notice`, `.error`, `pre` | miscellaneous pages/errors/debug | High | Medium | `components/notice.css`, `generic/base.css` |

## 4. Selector Usage Methodology

Commands used for audit included `rg`, `sed`, `nl`, `wc`, and read-only `python3` scripts. Static search covered:

- Jinja templates under `src/app/templates`.
- Python feature/presenter code under `src/app/features`.
- Project JavaScript under `src/app/static/js` excluding vendored HTMX/Alpine.
- Tests and fixtures under `tests`.

Dynamic usage patterns explicitly found:

- `src/app/templates/base.html:40`: Alpine `:class="{ 'nav-actions-open': navOpen }"`.
- `src/app/templates/ui/_action.html:4` and `src/app/templates/ui/_action.html:18`: `ui-action__button--{{ action.placement }}`, `action-{{ action.id }}`.
- `src/app/templates/imports/review/_item.html:4`: `review-item--status-{{ item.visual_state }}`.
- `src/app/templates/imports/review/_item.html:59`: `{{ item.money_tone }}`.
- `src/app/templates/imports/review/_item.html:68`: `tone-{{ item.state_badge.tone }}`.
- `src/app/templates/imports/review/_item.html:90`: `problem-{{ problem.tone }}`.
- `src/app/templates/imports/review/_panel_tab.html:3`: `review-panel__tab--{{ panel.role }}` and `review-panel__tab--{{ panel.panel_type }}`.
- `src/app/templates/imports/review/_panel_tab.html:7`: Alpine `x-bind:class="{ 'is-active': ... }"`.
- `src/app/templates/imports/review/_panel_drawer.html:3`: `review-panel__drawer--{{ panel.panel_type }}`.
- `src/app/templates/imports/index.html:36`: `import-document-card--{{ document.status_value }}`.
- `src/app/templates/imports/_raw_transaction_row.html:7`: `{{ row.status_css_class }}` from `src/app/features/imports/presentation/document_page/presenter.py:403`.
- `src/app/templates/imports/mapping/_preview_row.html:6` and `:11`: `{{ row.status_badge_class }}`, `{{ row.amount_class }}` from `src/app/features/imports/presentation/mapping/preview.py:139` and `:149`.
- `src/app/static/js/entity-target.js:1-13`: JS-owned classes `entity-target-cleared`, `manual-operation-row--target`, `entity-card--working`, and recent highlight classes.

Static search cannot prove absence when class names are formed from enum values, action IDs, tones, or visual state. Therefore this audit does not mark any selector as definitely safe to delete.

## 5. Global Styles and Implicit Dependencies

Most dangerous global dependencies:

- `body` background/text at `app.css:42-46` sets the only global theme surface.
- `.button, input, select` at `app.css:814-830` makes every form control share button-like geometry and transitions.
- `.form-panel .button, .primary-action` at `app.css:884-895` makes any button inside `.form-panel` primary/green unless overridden.
- `.field span` at `app.css:3294-3299` styles any span inside `.field`, which makes markup structure part of the visual API.
- `.table` and `.table th/td` at `app.css:3407-3424` are global and later overridden by `.table-scroll` and `.report-table`.
- `.badge-*`, `.tone-*`, `.amount-*` at `app.css:3311-3405` mix status, operation type, source, and money direction in one shared namespace.
- Responsive blocks at `app.css:6813-7550` override many unrelated modules from one place.

## 6. Legacy CSS Inventory

Legacy here means selectors that are broad, old-shape, duplicated by newer BEM components, or likely compensating for earlier layout choices.

| Block | Location | Likely users | Why legacy-like | Isolation strategy |
| --- | --- | --- | --- | --- |
| Generic form grid helpers | `app.css:926-1065` | imports upload/mapping, categories, older forms | Uses global `.form-panel .field` plus `!important` span helpers | Keep until each form family migrates to `operation-form`, `filter-form`, or feature form blocks |
| Category edit old layout | `app.css:1648-1690` | older category edit/detail flows | `category-name-field`, `category-primary-action` are layout helpers, not component API | Move to future `legacy/reference-forms.css`; delete only after category forms use BEM form classes |
| Generic entity card layer | `app.css:1724-2117` | categories, properties, workspaces, accounts | Mixes shared card, technical details, copy panel, account balance | Extract `entity-card` first, keep page-specific variants in page files |
| Technical/details variants | `app.css:1909-2066`, `5561-5816` | import debug, admin, actions, filter details | Several `details > summary` implementations with repeated marker hiding and plus/minus behavior | Create one `details-toggle` or `disclosure` component after reviewing markup |
| Rule legacy aliases | `app.css:4962-5000` | transaction rules | `rule-card-main`, `rule-card-title`, `rule-status` coexist with BEM `rule-card__*` around `app.css:3996-4208` | Keep in legacy until templates no longer render alias classes |
| Action aliases | `app.css:2976-3050`, `6202-6267`, `ui/_action.html` | row actions and review actions | `ui-action__button--*`, `action-primary`, `primary-action`, `.button-danger` all carry visual meaning | Define one action style contract; keep aliases during transition |

No legacy CSS was removed.

## 7. Specificity and Cascade Risks

Notable specificity risks:

- `app.css:1763`, `4102`, `5132`, `5315`: `html:not(.entity-target-cleared) ...:target` depends on JS removing a class in `src/app/static/js/entity-target.js`. It also outranks simple component states.
- `app.css:5132`: `.financial-row:target:not(.entity-card-current)` reaches across component ownership and target behavior.
- `app.css:5339` and `5353`: `.review-item__meta > span:not(...)` depends on immediate children and tag choice.
- `app.css:5718-5726`: multiple summary pseudo-element resets for review/filter/rule details depend on exact details nesting.
- `app.css:6153` and `6195-6198`: report table alignment depends on `th:not(:first-child)`, `td:last-child[data-label="прибыль"]`, and data-label text.
- `app.css:7510-7512`: mobile `.review-item__meta > span` globally sets width for all review item meta spans.

CSS IDs: none found.

Deep/structural selectors found: 55. Important examples:

- `app.css:233` `.panel > *`
- `app.css:751` `.import-page-actions .import-action-details > :not(summary)`
- `app.css:1839` `.entity-card-meta > span:not(.badge)`
- `app.css:3269-3285` `.table-scroll .table th:first-child`, `tr:last-child td`
- `app.css:6311-6317` `.review-panel-form > .review-panel-form__section` and sibling page-owned children
- `app.css:7382` `.report-table td:last-child`

Future BEM can solve many of these by moving structural expectations into named elements. Cascade layers can help with order, but they do not fix selectors that depend on accidental DOM structure.

## 8. !important Inventory

32 `!important` declarations were found.

| Lines | Declarations | Likely reason | Risk |
| --- | --- | --- | --- |
| 34 | `[x-cloak] display: none !important` | Alpine cloak must win before initialization | Low, acceptable with comment in future |
| 975, 990, 1017, 1021, 1025, 1029, 1033, 1037 | mapping/form grid spans | Overrides `.form-panel .field` grid defaults | Medium/high |
| 1084, 1198 | visually hidden file/radio inputs | Hiding native input while keeping accessible control | Low if documented |
| 1658, 1663, 1667 | category edit grid helpers | Old form grid override | Medium |
| 3144 | `.row-drawer__footer` grid span | Drawer footer must escape form grid | Medium |
| 3787, 3923, 3964, 3968 | rule form advanced/edit grid | Rule form overrides generic form grid | High |
| 4138, 4446, 4576, 4716, 4793 | visually hidden details summary controls | Native summary kept for semantics but hidden | Low/medium; should use shared utility |
| 5520, 5521, 5525, 5526 | `.problem-warning`, `.problem-danger` | Problem tone must override base signal styling | Medium; better as component modifier |
| 6272, 6274 | `.review-panel__drawer` max-width/margin | Counteracts inherited drawer/form constraints | High |
| 6866, 7429 | responsive form grid overrides | Mobile breakpoint override of generic grid | High |

The risky group is layout-related `!important`, especially forms and review drawer. These are candidates for module extraction, not immediate deletion.

## 9. Duplication Inventory

Representative duplication:

- Hidden accessible controls repeat at `app.css:1082-1093`, `1196-1207`, `4136-4148`, `4444-4456`, `4574-4586`, `4714-4726`, `4791-4803`. Real duplication. Future utility: `.u-visually-hidden-control` or component-owned hidden summary style.
- Recent feedback blocks repeat for rules, properties, and categories at `app.css:4008-4036`, `4222-4249`, `4265-4293`. Real duplication with same layout and values. Future component: `entity-feedback`.
- Create details/form shells repeat for rule/category/property/workspace at `app.css:3835-3858`, `4295-4342`, `4491-4538`, `4621-4668`. Mostly real duplication, with page-specific field spans.
- Action button states repeat between `.row-actions` (`app.css:2976-3050`) and `.review-item__actions` (`app.css:6447-6512`). Intentional variation, but should share semantic action tokens.
- Status colors repeat across `.badge-*`, `.tone-*`, `.money-*`, `.financial-row__meta-item--*`, `.review-item__state-token.tone-*`. This is not safe for global replacement because the same color can mean money direction, review state, or status tone.
- Table/card responsive logic repeats between generic `.table`, `.table-scroll`, import table cards, and report cards.

## 10. Unused CSS Candidates

Selector usage categories:

- Exactly unused: 0. Static analysis did not prove any selector impossible to use.
- Probably unused: 20 classes have no exact match and no detected dynamic prefix.
- Used dynamically: 90 classes have no exact match but match dynamic class patterns.
- Usage not established from runtime code: 32 exact class names were found only in tests; many are likely generated by templates at runtime from dynamic values.

Probably unused candidates:

- `account-tool-form__field--search` (`app.css:5898`, `7329`)
- `account-tool-form__fields--classification` (`app.css:5878`, `7006`, `7254`)
- `account-tool-form__fields--display` (`app.css:5883`, `7007`, `7255`)
- `account-tool-form__footer--filters` (`app.css:5937`)
- `account-tool-form__group--primary` (`app.css:5860`)
- `category-edit-form` (`app.css:1653`)
- `category-edit-layout` (`app.css:1648`)
- `category-lifecycle-actions` (`app.css:1674`, `1684`, `1688`, `7432`)
- `category-primary-action` (`app.css:1662`, `1670`, `7425`)
- `choice-grid` (`app.css:1244`)
- `compact-help-details` (`app.css:2387`, `5774`, `5781`)
- `document-detail-card-wide` (`app.css:3447`)
- `entity-card-current` (`app.css:1746`, also excluded in `app.css:5132`)
- `form-field-full` (`app.css:1036`, `6862`, `7421`)
- `form-submit` (`app.css:1040`, `6865`, `7428`)
- `health-row` (`app.css:131`, `346`)
- `import-document-name` (`app.css:514`)
- `row-actions__primary` (`app.css:2986`, `3013`, `3022`)
- `row-actions__secondary` (`app.css:2987`, `3030`, `3038`)
- `technical-value` (`app.css:3467`)

Do not delete these now. First confirm with rendered pages, dynamic class generation, and visual regression.

## 11. Dynamic Class Risks

Dynamic prefixes found:

- `badge-`: 16 template occurrences.
- `ui-action__button--`: 16 template occurrences.
- `action-`: 16 template occurrences.
- `financial-row__meta-item--`: 4 template occurrences.
- `amount-`: 3 template occurrences.
- `tone-`: 3 template occurrences.
- `review-item--status-`: 1 template occurrence.
- `review-panel__tab--`: 2 template occurrences.
- `review-panel__drawer--`: 1 template occurrence.
- JS constants in `entity-target.js`: `entity-target-cleared`, `entity-card--working`, `manual-operation-row--target`, `rule-card--recent`, `category-card--recent`, `property-card--recent`.

Risk: PurgeCSS or any static-only removal tool would remove valid status/action classes unless safelisted.

Minimum safelist families if a purge-like tool is used only for candidate discovery:

```text
badge-*
tone-*
amount-*
money-*
ui-action__button--*
ui-action__form--*
action-*
action-form-*
review-item--status-*
review-panel__tab--*
review-panel__drawer--*
financial-row__meta-item--*
account-movement__meta-item--*
manual-operation-row--*
account-movement--*
import-document-card--*
import-raw-row--*
problem-*
workflow-step-*
```

## 12. Hardcoded Values Inventory

Color inventory:

- 15 HEX values, all in `:root` (`app.css:3-17`). These are palette-like values.
- 2 `rgba(...)` values: dialog shadow/backdrop at `app.css:6580` and `app.css:6585`.
- 0 HSL/HSLA values.
- 200 unique `color-mix(...)` expressions, 422 total occurrences.
- 6 gradients.

Most repeated hardcoded/non-token values:

- `1px`: 192 occurrences.
- `8px`: 161 occurrences.
- `10px`: 116 occurrences.
- `12px`: 102 occurrences.
- `6px`: 96 occurrences.
- `0.78rem`: 36 occurrences.
- `0.72rem`: 16 occurrences.
- `0.68rem`: 14 occurrences.
- `border-radius: 8px`: 28 occurrences.
- `border-radius: 6px`: 27 occurrences.
- `box-shadow: inset 0 0 0 1px var(--target-ring)`: 5 occurrences.

Repeated `color-mix(...)` values:

- `color-mix(in srgb, var(--border) 72%, transparent)`: 20 occurrences.
- `color-mix(in srgb, var(--border) 78%, transparent)`: 16 occurrences.
- `color-mix(in srgb, var(--surface-strong) 54%, transparent)`: 12 occurrences.
- `color-mix(in srgb, var(--border) 58%, transparent)`: 10 occurrences.
- `color-mix(in srgb, var(--border) 82%, transparent)`: 9 occurrences.

Possible semantic roles for current root colors:

- `#11111b` / `--bg`: page background, overlay backdrop base, theme crust.
- `#181825` / `--surface`: default surface.
- `#1e1e2e` / `--surface-strong`: raised/strong surface.
- `#313244`, `#45475a`: selected/current/work surfaces.
- `#cdd6f4`: primary text.
- `#a6adc8`: muted/secondary text.
- `#89b4fa`: accent/info/transfer.
- `#b4befe`, `#74c7ec`: selected/current context accents.
- `#94e2d5`: help/info.
- `#a6e3a1`: success/income/primary action.
- `#f9e2af`: warning/attention/profit.
- `#f38ba8`: danger/expense/error.
- `#585b70`: default border.

Do not replace identical colors globally. For example, green currently means income, success, primary action, and current progress in different contexts.

## 13. Tokenization Readiness

Ready:

- The file already centralizes palette-like values in `:root`.
- Most component colors are expressed through variables, not raw HEX.
- Focus states exist (`app.css:843-849`).

Not ready:

- Variable names are color/palette names, not Booker Tee semantic names.
- Components directly use palette-ish variables (`--green`, `--danger`, `--accent`).
- Spacing, radius, font sizes, shadows, z-index, and breakpoints are mostly raw values.
- `color-mix(...)` expressions are component-local and often encode semantic meaning inline.
- Light theme risks are high because transparent mixes assume dark surfaces.

## 14. Proposed Token Hierarchy

Level 1: primitive tokens.

```css
--palette-neutral-0;
--palette-neutral-50;
--palette-neutral-100;
--palette-neutral-900;
--palette-blue-500;
--palette-lavender-500;
--palette-teal-500;
--palette-green-500;
--palette-yellow-500;
--palette-red-500;

--space-0;
--space-1;
--space-2;
--space-3;
--space-4;
--space-5;

--font-family-sans;
--font-family-mono;
--font-size-xs;
--font-size-sm;
--font-size-md;
--font-size-lg;
--font-size-xl;

--radius-none;
--radius-xs;
--radius-sm;
--radius-md;
--shadow-overlay;
--z-sticky;
--z-popover;
--z-dialog;
```

Level 2: semantic tokens.

```css
--color-page-background;
--color-surface;
--color-surface-raised;
--color-surface-muted;
--color-surface-hover;
--color-surface-active;
--color-surface-selected;
--color-surface-work;

--color-text-primary;
--color-text-secondary;
--color-text-muted;
--color-text-inverse;
--color-text-on-accent;

--color-border;
--color-border-muted;
--color-border-strong;
--color-border-focus;

--color-accent;
--color-accent-hover;
--color-info;
--color-help;
--color-success;
--color-warning;
--color-danger;

--color-money-income;
--color-money-expense;
--color-money-transfer;
--color-money-profit;

--color-status-active;
--color-status-muted;
--color-status-review;
--color-status-duplicate;
--color-status-confirmed;

--color-focus-ring;
--color-disabled-surface;
--color-disabled-text;
```

Level 3: component tokens, only where stable component contracts need them.

```css
--button-primary-surface;
--button-primary-border;
--button-danger-surface;
--badge-surface;
--financial-row-surface;
--financial-row-border;
--review-item-next-surface;
--review-item-problem-border;
--row-drawer-surface;
--dialog-backdrop;
```

Avoid tokens like `--catppuccin-gray`, `--purple-color`, or `--review-item-17px-gap`.

## 15. Theme Switching Architecture

Target chain:

```text
theme palette
-> Booker Tee semantic tokens
-> optional component tokens
-> BEM components
```

Theme CSS should own palette-to-semantic mapping:

```css
[data-theme="catppuccin-mocha"] {
  --color-page-background: var(--palette-mocha-crust);
  --color-surface: var(--palette-mocha-base);
  --color-text-primary: var(--palette-mocha-text);
  --color-accent: var(--palette-mocha-mauve);
}
```

Components should use:

```css
.review-item {
  background: var(--color-surface);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}
```

Theme selection should be resolved before first paint:

- Server renders `<html data-theme="...">`.
- Priority: explicit user setting, then cookie, then workspace/user default, then `prefers-color-scheme`.
- The compiled CSS contains default and named theme token blocks early in the bundle.
- Avoid client-only theme switching on initial load; it causes FOUC.

## 16. Light/Dark Theme Risks

High-risk areas for light themes:

- Transparent `color-mix(..., transparent)` surfaces throughout the file may become too low contrast on light backgrounds.
- Shadows use dark assumptions: `app.css:6580` dialog shadow and `app.css:769` action menu shadow.
- Backdrop uses Mocha raw color via `rgba(17, 17, 27, 0.76)` at `app.css:6585`.
- Border-only statuses (`badge-*`, `tone-*`) may be too subtle on light surfaces.
- Disabled state `.button-disabled` at `app.css:921-924` relies only on opacity/pointer-events.
- Hover states often only change color/background slightly; e.g. `app.css:837-841`, `879-882`.
- Table mobile transforms in `app.css:7342-7397` assume dark card surfaces.
- SVG icons use `currentcolor` via `.icon` at `app.css:52-57`, which is theme-compatible, but inline SVG generated by `icon()` should continue using currentColor only.
- Browser autofill styles are not explicitly handled.

## 17. Proposed File Structure

Recommended target structure:

```text
src/app/static/css/
├── app.css                  # generated or source entry during transition
├── settings/
│   ├── primitives.css
│   ├── semantic-tokens.css
│   └── component-tokens.css
├── themes/
│   ├── default.css
│   ├── catppuccin-latte.css
│   └── catppuccin-mocha.css
├── generic/
│   ├── reset.css
│   └── base.css
├── layout/
│   ├── app-shell.css
│   ├── page.css
│   └── responsive.css       # temporary only, shrinks over time
├── components/
│   ├── action.css
│   ├── badge.css
│   ├── button.css
│   ├── dialog.css
│   ├── empty-state.css
│   ├── entity-card.css
│   ├── financial-row.css
│   ├── form-field.css
│   ├── metric.css
│   ├── money.css
│   ├── row-actions.css
│   ├── row-drawer.css
│   └── review-item.css
├── pages/
│   ├── accounts.css
│   ├── dashboard.css
│   ├── import-detail.css
│   ├── import-mapping.css
│   ├── import-review.css
│   ├── manual-operations.css
│   ├── reference-data.css
│   ├── reports.css
│   ├── transaction-rules.css
│   └── workspaces.css
├── utilities/
│   ├── accessibility.css
│   └── text.css
└── legacy/
    └── legacy.css
```

Rules:

- `settings`: tokens only, no selectors except `:root`, theme roots, or `[data-theme]`.
- `themes`: palette and semantic token values only; no component selectors.
- `generic`: reset/base HTML element rules.
- `layout`: app shell, page frame, global layout primitives.
- `components`: reusable BEM blocks. No page selectors reaching into component internals.
- `pages`: page composition and page-only components. May set layout around components, not override internals casually.
- `utilities`: tiny single-purpose classes; no business meaning.
- `legacy`: old selectors only. Do not add new feature CSS here.

Load order:

```text
settings/primitives
themes/default and named theme mappings
settings/semantic-tokens
settings/component-tokens
generic
layout
legacy
components
pages
utilities
```

## 18. Build and FOUC Prevention

Current simplest production behavior is good: one CSS file in the head.

Options:

- Simplest: keep editing `app.css` during early migration, but add source modules later and concatenate them with a tiny script. Low tooling, but weak CSS validation.
- Most reliable: PostCSS with `postcss-import` and optional `postcss-preset-env`, producing one compiled `app.css`. Compatible with SSR and no SPA framework.
- Heavier option: Vite or esbuild CSS bundling. Useful only if JS asset bundling also becomes necessary.
- Sass: useful for partials, but CSS custom properties and PostCSS are enough for the stated theming goal.

Recommended for this project:

1. Add PostCSS only when the first component module is ready.
2. Keep `src/app/templates/base.html:7` loading one compiled `app.css`.
3. Keep mtime cache-busting or replace with manifest hashing later.
4. Avoid runtime browser `@import`.
5. Render `data-theme` server-side before first paint.

## 19. Cascade Layers Assessment

`@layer` can help once modules exist, but it is risky to wrap the current file wholesale.

Suggested layer order:

```css
@layer reset, themes, tokens, base, legacy, layout, components, pages, utilities;
```

Assessment:

- Helpful for keeping legacy below components even when legacy loads later.
- Helpful for preventing page CSS from accidentally outranking components.
- Risk: unlayered CSS outranks layered CSS. During gradual migration, old unlayered `app.css` can beat new layered modules unless the migration boundary is controlled.
- Risk: wrapping all existing CSS in `legacy` changes order relative to future unlayered third-party CSS and can expose hidden dependencies.
- Third-party CSS should either remain unlayered and loaded before project CSS, or be wrapped in a documented `vendor` layer.

Gradual plan:

1. Do not wrap the existing file yet.
2. Introduce layers only in the new source entry when build exists.
3. Move one migrated component into `@layer components`.
4. Keep old selectors for that component in `@layer legacy` only when their behavior has screenshot coverage.

## 20. Proposed BEM Conventions

Block:

- Stable reusable UI concept: `review-item`, `financial-row`, `row-actions`, `row-drawer`, `badge`, `operation-form`.

Element:

- Part owned by the block: `review-item__amount`, `row-drawer__footer`.
- Avoid reaching into child components with selectors like `.page .component__element`.

Modifier:

- Stable visual or structural variant: `review-item--next`, `operation-form--drawer`.
- Presenter-generated finite visual state can use modifier if class names are explicitly enumerated: `review-item--status-confirmed`.

State:

- UI state not part of component identity: `.is-active`, `.is-loading`, `.is-open`.
- Current code uses `is-active` from Alpine in `src/app/templates/imports/review/_panel_tab.html:7`.

Data attributes:

- Use for IDs, behavior, and state consumed by JS/HTMX: `data-entity-working`, `data-review-panel-url`, `data-review-panel-loaded`.
- Prefer `data-state="duplicate"` when the state is primarily data and multiple components may react to it.
- Prefer `.review-item--status-duplicate` when the ViewModel intentionally exposes a finite visual API for one component.

Hooks:

- CSS class: `.review-item__action`.
- JS hook: `.js-review-action` only if needed.
- Data: `data-review-item-id`.
- HTMX behavior should stay as attributes near the owned partial until repeated abstraction proves useful.

Page classes:

- Page root classes such as `.import-review-page` may set page layout variables or page grid.
- Page CSS must not override internals of shared components without a documented reason.

## 21. Candidate Components for First Migration

| Candidate | Selectors | Templates | ViewModel/code | States/interactions | Rules approx. | Isolation | Risk | Fit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Review Item | `.review-item*`, `.review-panel*`, `.review-actions*`, `.problem-*` | `imports/review/_item.html`, `_action_set.html`, `_panel_*` | `imports/presentation/review/item.py`, `actions.py`, `models.py` | visual states, HTMX row swap, Alpine panels, lazy drawers | 120+ | Medium | High | Best strategic candidate |
| Row Actions | `.row-actions*`, `.ui-action__button--*`, `.action-*` | `ui/_action.html`, ledger/account/review action partials | shared `ActionVM` patterns | primary/secondary/danger/link/post/submit | 35+ | Medium | High | Good after Review Item or alongside tests |
| Badge/Tone | `.badge-*`, `.tone-*`, `.amount-*` | many templates | many presenters/status tones | dynamic classes from enums | 45+ | Low | High | Needs token foundation first |
| Empty State | `.empty-state*` | `components/empty_state.html` | simple macro callers | primary/secondary actions, responsive | 15+ | High | Low | Good low-risk pilot, but less valuable for core flow |
| Transaction Rule Card | `.rule-card*`, `.rule-form*`, `.rule-list*` | `transaction_rules/*` | transaction rules presenter | HTMX row/list swaps, drawer loading | 100+ | Medium | Medium/high | Good second vertical slice |

## 22. Review Item Assessment

Why it is the preferred first serious migration:

- It is central to the import/review flow.
- It already uses a BEM-ish root and elements at `app.css:5288-5560`.
- It has a clear ViewModel contract in `src/app/features/imports/presentation/review/item.py:206-276`.
- It exercises the real architecture: visual state, action policy, HTMX partial replacement, Alpine local state, lazy drawers, problem signals.

Risks:

- It shares `financial-row` at `app.css:5115-5286` with manual operations and account movements.
- Actions come from shared `ui/_action.html`, so changing review action styles can affect ledger/account rows.
- Panel/drawer styles at `app.css:5561-6705` are interwoven with generic `action-details`, `filter-details`, and `row-drawer`.
- Mobile rules at `app.css:6813-7550` include review-specific overrides far from the component block.
- `problem-warning` and `problem-danger` use `!important` at `app.css:5519-5526`.

Review Item states to fixture before migration:

- `needs_review`
- `ready_to_confirm`
- `suggested`
- `possible_duplicate`
- `duplicate`
- `confirmed`
- `matched`
- `ignored`
- `failed` / normalization error

Also fixture:

- primary, secondary, and danger actions;
- operation link/outcome summary;
- category and transfer panels open;
- lazy drawer placeholder;
- long description;
- missing category;
- parse error/problem signals;
- mobile layout at 560px and desktop at 1280px.

## 23. Recommended Migration Order

1. Audit.
   - Goal: document current risk and selectors.
   - Done when this file is reviewed.
   - Commit size: one docs commit.
   - Rollback: delete docs file.

2. Freeze CSS behavior.
   - Goal: capture screenshots for core pages before any move.
   - Changes: add Playwright screenshot fixtures/tests only.
   - Risk: test setup friction.
   - Done when baseline screenshots run locally.
   - Commit size: test infra plus fixtures.
   - Rollback: remove screenshot tests.

3. Minimal token foundation.
   - Goal: introduce semantic aliases without visual changes.
   - Changes: add semantic tokens mapped to current variables.
   - Risk: accidental visual changes if replacement is broad.
   - Done when limited selectors use aliases and screenshots match.
   - Commit size: small, one token family at a time.

4. Build preparation.
   - Goal: allow source modules compiled into one CSS file.
   - Changes: PostCSS import build and docs.
   - Risk: FOUC/cache mistakes.
   - Done when app still loads one generated CSS file.
   - Commit size: tooling-only.

5. Pilot component.
   - Goal: migrate one low-risk component such as `empty-state` or a strict slice of `review-item`.
   - Changes: component module, same selectors initially.
   - Risk: duplicate order mistakes.
   - Done when screenshots match.
   - Commit size: one component.

6. Review Item vertical slice.
   - Goal: migrate review item component plus related panels/actions only where owned.
   - Changes: component CSS, semantic tokens, test coverage.
   - Risk: shared action/financial row regressions.
   - Done when all review item states and mobile screenshots match.
   - Commit size: split into core, panels, actions if needed.

7. Next components.
   - Goal: transaction rule card, row actions, badge/money tokens.
   - Commit size: one component/page slice per commit.

8. Isolate legacy.
   - Goal: move remaining old selectors to `legacy/legacy.css` with no visual changes.
   - Risk: cascade order.
   - Done when screenshots match.

9. Delete confirmed unused CSS.
   - Goal: remove replaced selectors only.
   - Done in separate deletion commits.

10. Add additional themes.
   - Goal: Catppuccin Latte/Mocha and default theme.
   - Only after semantic tokens cover migrated components.

## 24. Visual Regression Strategy

Use Playwright when test setup is approved. Minimum scenarios:

- desktop 1280x900;
- mobile 390x844;
- long content;
- empty values;
- hover/focus/disabled states;
- validation error;
- HTMX loading placeholder;
- open drawer/panel;
- dark default;
- future light theme once tokens exist.

Review Item fixtures:

- one screenshot per visual state;
- one with category panel open;
- one with transfer panel open;
- one with danger menu open;
- one with linked operation summary;
- one with long description and small viewport.

## 25. CSS Deletion Safety Process

Every deletion should be its own commit after replacement has shipped.

Required report format:

```text
Deleted selector:
Reason:
Where usage was searched:
Dynamic class checks:
Replacement selector/style:
States checked:
Screenshots/tests run:
Rollback:
```

Never use PurgeCSS as source of truth. It may be used only to generate candidates with a safelist.

## 26. Coding Rules for Future CSS

1. New component CSS uses BEM.
2. New components use semantic tokens.
3. Components do not use variables named after a concrete theme.
4. Do not use ID selectors in CSS.
5. Do not use `!important` without a documented reason.
6. Avoid styling components through HTML tags.
7. Avoid deep nesting and accidental DOM structure dependencies.
8. Page CSS does not silently override shared component internals.
9. Legacy CSS does not grow new feature styles.
10. JS hooks are not visual API unless explicitly documented.
11. Focus states must be visible.
12. Hover must not be the only available-action signal.
13. Color must not be the only status signal.
14. All new components should be light/dark-theme ready.
15. New themes must not require component CSS edits.
16. Do not create a token for every one-off value.
17. Do not name semantic tokens by concrete colors.
18. Do not globally replace identical HEX/color values without context.
19. CSS changes should be small, isolated commits.

## 27. Risks and Unresolved Questions

- Does the project want generated CSS committed, source CSS committed, or both?
- Should `app.css` remain the generated production artifact or become the source entry?
- Which pages are mandatory for first screenshot coverage?
- Should the first low-risk pilot be `empty-state`, or should work start directly with `review-item` because it is the highest-value component?
- Should `entity-card-current` be retained as a public component state even though static search did not find direct runtime use?
- Should `--green` remain "success" or split immediately into `--color-money-income` and `--color-action-primary` aliases?

## 28. Recommended Next Task for Codex

Do not refactor yet.

Recommended exact next task:

```text
Add a read-only CSS selector inventory artifact or Playwright baseline plan for Review Item states, without changing app.css or templates.
```

The first implementation task after that should be:

```text
Introduce semantic token aliases mapped to the current :root variables, then migrate only Review Item color references to those aliases with screenshot checks.
```
