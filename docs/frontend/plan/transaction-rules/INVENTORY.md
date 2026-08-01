# Transaction Rules inventory

Статус: audited baseline observed 2026-08-01. Найденные contract defects из
этого baseline исправлены в Slice 0 2026-08-02; текущее поведение определяют
код, tests и completion record в [`README.md`](README.md).

## Runtime map

```text
SSR GET/POST /rules*
  -> transaction_rules/router.py + router_forms.py
  -> TransactionRuleQueryUseCase / ManagementUseCase / Seeder
  -> TransactionRuleRepository
  -> TransactionRule model
  -> presenter/ViewModels
  -> Jinja + HTMX + legacy CSS/JS

Known parser / unknown mapping
  -> TransactionRuleApplicationUseCase
  -> suggestions on RawTransaction

React Import Review / Chat review
  -> shared ImportReviewRuleCreator
  -> ManagementUseCase._create_rule
  -> apply new rule to eligible sibling rows
```

## Legacy browser routes

Router prefix: `/rules`, tag: `transaction-rules`.

| Method | Route | Permission | Behavior |
| --- | --- | --- | --- |
| GET | `/rules` | authenticated workspace member | list, filters, counts, create form, read-only mode |
| POST | `/rules` | financial write | create or silently return weakly matching existing rule |
| POST | `/rules/seed-defaults` | financial write | create categories/rules and commit |
| GET | `/rules/{rule_id}/edit` | financial write | lazy HTMX edit form |
| POST | `/rules/{rule_id}` | financial write | update and commit |
| POST | `/rules/{rule_id}/toggle` | financial write | enable/disable and commit |
| POST | `/rules/{rule_id}/delete` | financial write | unconditional hard delete and commit |

Non-HTMX mutations redirect with `303`. Create/update/toggle target
`/rules#rule-<uuid>`; delete targets `/rules`. HTMX swaps either one row or the
entire `#rules-list-panel`.

There is no `/api/v1/transaction-rules` CRUD API. Legacy HTML/form endpoints
are currently exported in `frontend/openapi.json` and generated TypeScript even
though React cannot consume their HTML/form contract safely.

## GET behavior and filters

Inputs:

- `q`: normalized case-insensitive substring over rule name, pattern, category
  name and property name;
- `category_id`: UUID; malformed value returns HTML route `400`;
- `status`: `all | active | inactive`; unknown value becomes `all`;
- `limit`: clamped to `1..1000`, default/increment `50`.

Repository loads every workspace rule with category/property/account
relationships, ordered by `priority, name`. Filtering, counts and limiting then
happen in Python. A newly created rule can be appended beyond the limit so the
anchor remains visible.

Observed defects:

- `build_rules_page()` calls `CategoryService.list_or_seed_defaults()`, which
  commits category seeding during GET;
- `RulesPageVM.inactive_rule_count` is derived from visible rows minus a global
  active count and can become wrong/negative on a limited or filtered page;
- Russian count copy is not pluralized correctly;
- the list has no true server pagination or stable page boundary.

## Form surface

Create/edit expose:

- optional display name;
- required pattern;
- match type `contains | exact`;
- application mode `suggest | auto_apply`;
- direction `inflow | outflow | any`;
- optional min/max absolute amount;
- optional target operation type;
- optional category and property.

Create defaults are `contains`, `suggest`, `any`, and `expense`. Category and
Property options include only active references. Edit lazily loads the same
active lists.

Persistence fields not exposed by SSR:

- `account_id` — affects matching;
- `priority` — affects equal-score order;
- `auto_description` — persisted but not applied;
- `affects_profit` — persisted but not used by suggestion/posting flow.

Update intentionally leaves these dormant values unchanged, but a historical
archived target can disappear from the edit select and be cleared accidentally
when another field is saved.

## Management behavior

### Create

1. Category and property resolve inside current workspace.
2. Pattern whitespace is cleaned and then silently truncated to 255 chars.
3. Blank name is generated from pattern/category/operation type.
4. `find_existing(workspace, pattern, category)` can return an existing rule.
5. Otherwise a new active rule at priority 100 is inserted and committed.

Weak duplicate identity ignores match type, mode, direction, amount, property,
operation type and account. Concurrent create has no DB uniqueness guard.

### Update

Workspace-scoped rule lookup and category/property validation exist. The
operation updates name, pattern, match type, category, property, operation type,
direction, mode and amounts, then commits. It has no stale token and does not
validate amount range.

### Toggle

Workspace-scoped lookup exists, but activation does not revalidate whether its
category/property target is still available for new references.

### Delete

Workspace-scoped lookup exists. Any active/disabled rule can be hard-deleted;
no impact count, expected version or dependency policy is checked.

## Matching and winner selection

A rule matches only when:

- `raw.workspace_id == rule.workspace_id`;
- optional account matches;
- direction matches the sign (`any` bypasses it);
- min/max compare against `abs(amount)`;
- normalized description has exact equality or contains normalized pattern.

Normalization case-folds, converts punctuation to spaces and drops purely
numeric tokens. Creation does not reject a pattern that normalizes to empty.

Only active rules are loaded. For every eligible raw row, the application first
clears the previous rule suggestion, chooses one best rule, writes new
suggestion fields/payload, and flushes without committing. Caller owns the
transaction.

Eligibility excludes linked rows and terminal/non-suggestable statuses. The
specificity tuple is:

```text
has category
has property
has operation type
has account
has amount bound
```

Equal specificity keeps the first repository-ordered match. `priority` is
therefore only an indirect tie breaker; exact matching and pattern length are
not preferred.

## Suggestion evidence

Application writes:

- `suggested_category_id`;
- `suggested_property_id`;
- `suggested_operation_type`;
- `suggested_by_rule_id`;
- bounded `raw_payload.rule_suggestion` snapshot with rule id/name/pattern/mode
  and target ids.

Status moves `normalized -> suggested`; clearing moves only
`suggested -> normalized`. Other review/problem states remain their state while
their suggestion fields can change.

`RawTransaction.suggested_by_rule_id` uses `ON DELETE SET NULL`, while category
and property suggestion references remain. The payload snapshot is not cleared
on rule delete.

## Import Review influence

Rules are applied at four points:

1. after known parser creates and deduplicates raw rows;
2. after unknown mapping creates and deduplicates raw rows;
3. explicit React action `POST .../apply-rules` over eligible rows;
4. after the user confirms a row with “remember rule”, over eligible sibling
   rows in the same document.

The read model exposes rule id/name/pattern/mode, suggested classification and
target references. `suggest` and `auto_apply` both prefill suggestion facts.
`auto_apply` additionally allows a fully confirmable row to expose quick
confirmation, but still requires explicit user action and the same server
posting checks.

Before posting, Import Review rechecks:

- expected raw status and linked state;
- income/expense amount direction;
- category/property/account workspace ownership;
- confirmability and duplicate evidence;
- idempotency and DB race guard;
- document lifecycle and validation.

Transfer remains a separate server-owned workflow. Rules never call ledger
posting directly.

Editing, disabling or deleting a rule does not retroactively rewrite existing
suggestions. Explicit “Apply rules” is the current recalculation action.

## Reference lifecycle interactions

### Categories

- active category with active rules cannot be archived;
- disabled rules may keep a reference to an archived category;
- category delete is blocked by any rule reference and raw suggestion;
- current rule activation can incorrectly re-enable a rule whose category was
  archived while the rule was disabled;
- Categories detail and archive blocker link to `/rules` with category query or
  `#rule-<uuid>` anchor.

### Properties

- archive intentionally does not disable existing active rules;
- an active rule can continue suggesting an archived property;
- active pickers hide the property, but management lookup accepts it;
- an edit form that omits the current archived property can accidentally clear
  the relation.

The React migration must preserve accepted Categories/Properties decisions and
make re-enable/edit behavior explicit rather than silently changing targets.

## Workspace isolation

Current strengths:

- list/get/category preview repository queries filter `workspace_id`;
- matching also compares workspace ids;
- Category and Property target resolution is workspace-scoped;
- Import Review document/item and Chat conversation state are workspace-scoped;
- writer dependency is `require_financial_write_context`.

Gap:

- `CreateTransactionRuleCommand.account_id` is persisted without resolving an
  Account through the current workspace. SSR does not expose it, but application
  code must close this latent cross-workspace path before it becomes an API.

Wrong-workspace entity IDs should remain indistinguishable from unavailable
entities and must not reveal foreign names/counts.

## Seed defaults

`DefaultMerchantRuleSeeder` has a fixed merchant/category list. It creates
missing custom categories and expense/outflow rules in `auto_apply` mode.

Identity is normalized pattern plus category. Repeated execution normally
avoids duplicates, but if a matching user rule exists the seeder mutates its
application mode to `auto_apply`. This contradicts current confirmation copy:
“Ваши правила не будут изменены.” No concurrent uniqueness guard exists.

## Legacy and non-SSR consumers

Keep after presentation migration:

- known statement processing;
- unknown mapping import;
- Import Review rule application, suggestion DTO and atomic “remember rule”;
- Chat review rule creation/pattern validation and continuation;
- Category directory/detail counts, preview and lifecycle blockers;
- Workspace relationship and RawTransaction foreign key;
- migrations and pure/domain/application tests.

Browser consumers to retarget:

- React shell link `/rules` becomes a React route;
- Categories query/hash links continue against the canonical React route;
- Import Review currently links to the nonexistent `/transaction-rules` and
  must use `/rules` in the SPA;
- legacy `base.html` can keep `/rules` only as a historical redirect while
  other SSR pages remain;
- `scripts/ui_audit.py` must replace SSR selectors/scenario with React evidence.

## Local read-only data measurement

Read-only PostgreSQL audit on 2026-08-01:

| Fact | Result |
| --- | ---: |
| rules | 1649 |
| workspaces with rules | 1510 |
| max rules in one workspace | 69 |
| median rules per workspace | 1 |
| active rules | 1649 |
| raw rows with direct rule reference | 549 |
| referenced rows already linked to operations | 180 |
| account/custom priority/amount/auto-description/non-default profit fields | 0 |
| transfer/adjustment targets | 0 |
| duplicate `workspace + lower(pattern) + category` groups | 0 |
| cross-workspace targets | 0 |

Это measurement локальной dev/test БД, не доказательство production shape.
Перед cutover нужен equivalent read-only production-shaped check.

## Existing tests and gaps

Covered:

- contains/exact-adjacent normalization, direction and suggestion payload;
- auto-apply marker;
- merchant pattern inference and default seeds;
- specificity preference for categorized rule;
- in-memory filters/limit/recent pin;
- presenter/template layout, lazy edit, read-only state and anchors;
- Import Review authoritative reapply, confirm rollback and rule error mapping;
- suggestion DTO, quick confirm and restored status behavior;
- Chat pattern selection/create/commit behavior;
- Categories active-rule archive blocker and rule preview.

Not covered by Transaction Rules ownership tests:

- management/repository commit and rollback behavior;
- route/API auth, CSRF, 404/403/409/422 contracts;
- workspace isolation for every target and mutation;
- stale update/toggle/delete;
- amount/pattern/name validation;
- archived target activation/edit policy;
- rule delete impact and raw provenance;
- seed promise, concurrent idempotency and summary;
- DB pagination/count accuracy;
- end-to-end effect on known parser, mapping, manual reapply and Chat after
  rule lifecycle changes.
