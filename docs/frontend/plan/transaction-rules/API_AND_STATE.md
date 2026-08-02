# Transaction Rules API and state architecture

Статус: approved 2026-08-02 вместе с D1–D7 из [`README.md`](README.md).

## Boundary

```text
React route adapter
  -> feature API adapter + runtime validation
  -> /api/v1/transaction-rules
  -> API router/schemas/dependencies
  -> application query/command actor
  -> pure domain policies + workspace repositories
  -> SQLAlchemy models
```

API не вызывает legacy router, не сериализует presenter/ORM и не возвращает
URLs, Russian labels или CSS tones. Application/API data uses project Pydantic
models; technical dependency containers may remain dataclasses.

## Proposed server modules

```text
src/app/features/transaction_rules/
  application/
    directory.py          list projection, counts, references, capabilities
    rule_management.py    create/update/lifecycle/delete orchestration
    rule_application.py   existing suggestion workflow
    fixture_seeding.py    corrected idempotent explicit seed mutation
  domain/
    matching.py           existing pure matching
    suggestions.py        existing suggestion state
    validation.py         rule command/range/activation/delete policies
  schemas.py              commands, DTOs, reason codes
  repository.py           workspace queries, pagination, counts, impact
  models.py               persistence only

src/app/api/v1/transaction_rules/
  dependencies.py
  parameters.py
  router.py
  schemas.py
```

Do not split files mechanically. These names describe responsibilities; final
module boundaries should follow actual cohesion.

## Directory endpoint

```http
GET /api/v1/transaction-rules
  ?q=
  &category_id=<uuid>
  &status=all|active|disabled
  &page=1
  &page_size=50
```

Response shape:

```json
{
  "items": [
    {
      "id": "uuid",
      "name": "OZON → Маркетплейсы",
      "priority": 20,
      "isActive": true,
      "updatedAt": "ISO-8601",
      "condition": {
        "pattern": "OZON",
        "matchType": "contains",
        "direction": "outflow",
        "account": null,
        "amountMin": null,
        "amountMax": null
      },
      "outcome": {
        "operationType": "expense",
        "category": {"id": "uuid", "name": "Маркетплейсы", "isActive": true},
        "property": null,
        "applicationMode": "suggest",
        "autoDescription": null,
        "affectsProfit": true
      },
      "usage": {"directRawSuggestionCount": 4},
      "capabilities": {
        "canUpdate": true,
        "canEnable": false,
        "canDisable": true,
        "canDelete": false,
        "enableBlockedReasonCode": null,
        "deleteBlockedReasonCode": "raw_suggestions"
      }
    }
  ],
  "page": {"page": 1, "pageSize": 50, "total": 69, "totalPages": 2},
  "counts": {"all": 69, "active": 61, "disabled": 8},
  "appliedFilters": {"q": null, "categoryId": null, "status": "all"},
  "references": {
    "categories": [],
    "properties": []
  },
  "capabilities": {
    "canCreate": true,
    "canSeedDefaults": true,
    "readonlyReasonCode": null
  }
}
```

DTO may be flattened if that is clearer in final Pydantic/TypeScript, but these
facts and ownership boundaries remain. Reference items include active choices
plus a current archived reference required to render/edit a returned rule.

Counts come from the same workspace/search/category contract and do not derive
from the visible page in React; status is intentionally excluded from tab
counts, while `page.total` includes it. Search/filter/order execute in SQL. Sort remains
`priority, name, id` until a separate matching/order decision.

## Mutation endpoints

### Create

```http
POST /api/v1/transaction-rules
X-CSRF-Token: ...
Idempotency-Key: <uuid>
```

Request contains only first-slice editable fields. Response `201` is the
committed `TransactionRuleSummaryApiResponse`.

Create rules:

- require UUID `Idempotency-Key`; API rule id is deterministically derived
  from workspace and key, so the same key is isolated between workspaces;
- exact normalized replay returns the same committed rule with `replayed=true`;
- reuse with a different payload returns
  `transaction_rule_create_replay_conflict`;

- normalize whitespace but reject >255 rather than silently truncate;
- require pattern whose matching normalization is non-empty;
- amount bounds are non-negative Decimal strings and `min <= max`;
- selected target ids resolve in current workspace and are available for new
  reference;
- no weak `pattern + category` silent reuse;
- exact retry uses idempotency contract; a distinct semantically duplicate
  command gets stable conflict with existing rule id only if a full duplicate
  identity is deliberately defined.

### Update

```http
PUT /api/v1/transaction-rules/{rule_id}
```

Request includes `expectedUpdatedAt`. Server loads rule inside workspace,
checks stale token, resolves targets and returns committed summary. Dormant
fields not in request remain unchanged.

### Lifecycle

```http
POST /api/v1/transaction-rules/{rule_id}/disable
POST /api/v1/transaction-rules/{rule_id}/enable
```

Request includes expected active state and `expectedUpdatedAt`. Disable is
reversible and does not clear existing suggestions. Enable revalidates targets
and returns typed blocker codes such as `category_inactive`,
`property_archived`, `account_unavailable` according to approved policy.

Wrong-direction repeated action is a conflict/replay decision, not a blind
toggle boolean. Explicit verbs prevent stale “toggle” from reversing an
unexpected current state.

### Delete

```http
DELETE /api/v1/transaction-rules/{rule_id}
```

Body contains `expectedUpdatedAt`. Server requires disabled state and zero
direct raw references. Success returns only deleted id/name; directory state is
updated locally and can be reloaded authoritatively on conflict.

### Seed defaults

```http
POST /api/v1/transaction-rules/seed-defaults
```

Response:

```json
{
  "createdRules": 12,
  "existingRules": 42,
  "createdCategories": 0,
  "directory": {"...": "optional smallest consistent snapshot"}
}
```

Prefer counts plus a directory reload unless measurement proves returning the
full snapshot is cheaper/clearer. Existing rules are not mutated.

## Error contract

Use the common API envelope and stable codes:

| HTTP | Example code | Meaning |
| --- | --- | --- |
| 401 | common | unauthenticated |
| 403 | common | no financial-write capability |
| 404 | `transaction_rule_not_found` | missing or foreign-workspace rule |
| 409 | `transaction_rule_update_conflict` | stale editor |
| 409 | `transaction_rule_lifecycle_conflict` | stale/wrong lifecycle |
| 409 | `transaction_rule_delete_conflict` | stale delete |
| 409 | `transaction_rule_create_replay_conflict` | idempotency key reused differently |
| 422 | `transaction_rule_validation_error` | field errors |
| 422 | `transaction_rule_enable_blocked` | inactive/unavailable target |
| 422 | `transaction_rule_delete_blocked` | active or referenced rule |

Field keys use API camelCase (`pattern`, `amountMin`, `categoryId`, etc.). No
raw SQL/FK/private payload reaches response.

## Capabilities and policy ownership

Server computes:

- can create/seed/update/enable/disable/delete;
- lifecycle/delete blockers and direct reference count;
- whether current archived target can be retained;
- read-only reason;
- committed timestamps and state.

React owns:

- wording, icon, action placement and confirmation copy;
- which server-provided action appears primary/overflow;
- local draft dirty/pending/error state;
- Toast and focus behavior.

React never infers delete from `count === 0` or enable from `isActive=false`.

## Application transaction boundaries

- directory GET is side-effect free and never seeds categories;
- create/update/lifecycle/delete/seed each own one commit/rollback boundary;
- Import Review “confirm + remember rule + apply to siblings + post ledger +
  refresh validation/document” remains one outer transaction;
- Chat create/apply remains caller-owned and atomic with conversation state;
- `TransactionRuleApplicationUseCase` flushes only and never commits;
- unexpected exceptions roll back and propagate to safe 5xx.

Management actor should not commit from a private helper used by Import Review.
Prefer explicit transaction-owning public commands plus an internal
caller-transaction method whose contract is named and tested.

## Workspace and reference resolution

Every repository method receives `workspace_id`. Single entity lookup uses id
and workspace together. Target resolution rules:

- category: current workspace; active for create/enable/new target;
- property: current workspace; active for create/new target; approved handling
  for existing archived property is explicit;
- account, even while dormant: current workspace and valid reference state;
- created-by user identity comes from authenticated context, never request.

Cross-workspace target id maps to the same safe not-available field error and
does not disclose the foreign entity.

DB foreign keys alone are insufficient because they do not encode matching
workspace ownership.

## State ownership

### URL

```text
q, category_id, status, page, page_size, #rule-id
```

URL parser normalizes invalid status/page/page size and builds deterministic
links. Applying search/filter resets `page=1`. Back/Forward restores applied
filters/page; local draft is not written into URL.

### Route loader/server snapshot

- validated directory DTO;
- page/count/reference/capability facts;
- session/CSRF snapshot.

No global cache library is needed.

### Feature-local state

- current committed item collection after mutations;
- create panel draft/open/dirty/pending/errors;
- one edit expansion draft/trigger/dirty/pending/errors;
- lifecycle/delete/seed confirmation candidate;
- conflict recovery intent;
- Toast queue;
- filter draft before URL Apply.

### Server-only truth

- matching algorithm and priority order;
- active state and updated timestamp;
- workspace authorization;
- target availability;
- raw reference count and delete capability;
- suggestion recalculation;
- confirmability, dedupe, posting and financial meaning.

## Reconciliation rules

- create inserts returned committed item, navigates to stable anchor and may
  reload counts/page if item is outside current filter;
- update replaces exactly one item with server response;
- enable/disable replaces one item and lets URL filter decide visibility;
- delete removes returned id only after success;
- seed reloads authoritative directory/counts;
- conflict reloads directory or item before user retries;
- no optimistic mutation of rule lifecycle or usage counts.

If a mutation makes the current page empty, normalize to the last valid page.

## Frontend modules

```text
frontend/app/routes/
  transaction-rules.tsx
  transaction-rules-loader.ts

frontend/app/features/transaction-rules/
  api/transaction-rules-api.ts
  transaction-rules-page.tsx
  transaction-rules-page.module.css
  transaction-rule-records.tsx
  transaction-rule-form.tsx
  transaction-rule-create-panel.tsx
  transaction-rule-edit-panel.tsx
  transaction-rule-list-query.ts
  use-transaction-rule-editor.ts
  use-transaction-rule-lifecycle.ts
  use-transaction-rule-seeding.ts
  README.md
```

Extract hooks only where they own a real async/interaction responsibility.
Keep generated OpenAPI types compile-time, Zod validation at network boundary,
and explicit discriminated result unions.
