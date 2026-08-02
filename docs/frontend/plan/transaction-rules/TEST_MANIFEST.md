# Transaction Rules test and evidence manifest

Статус: approved replacement coverage с 2026-08-02. Existing tests are not
deleted until the corresponding owner test below exists and passes.

## Server domain tests

Preserve/extend characterization for:

- contains/exact normalization and numeric-token behavior;
- workspace/account/direction/absolute amount matching;
- missing amount behavior with/without bounds;
- winner specificity and equal-score priority/created-at order;
- inactive rule exclusion;
- eligible raw statuses and linked-row exclusion;
- apply/clear suggestion payload and status transitions;
- `suggest` versus `auto_apply` marker without silent posting;
- pattern inference used by Import Review and Chat;
- invalid empty-normalized pattern and amount ranges.

No React/API test replaces these pure policy tests.

## Application/repository tests

Add focused tests for:

- side-effect-free directory read;
- SQL search/category/status/order/page/count accuracy;
- workspace isolation on list/get/create/update/lifecycle/delete;
- Category/Property/Account target resolution;
- current archived target projection and preservation;
- create normalization, full duplicate/idempotency decision and rollback;
- update preserves dormant fields and rejects stale snapshot;
- explicit enable/disable wrong-state and stale conflicts;
- activation blocker policy for archived/unavailable targets;
- disable leaves existing raw suggestions unchanged;
- delete blocks active/referenced rules and removes only unused disabled rule;
- delete/reference race guard under PostgreSQL;
- seed creates missing only, is repeat-safe and never mutates existing rule;
- application use case flushes without taking caller transaction.

## Cross-feature financial/import regressions

Required:

- known parser: dedupe then rule suggestion; no confirmed Operation;
- unknown mapping: mapped rows become reviewable and get rules once;
- manual Apply rules clears/recalculates eligible siblings and returns
  authoritative review;
- possible duplicate remains blocked despite a matching rule;
- auto-applied suggestion quick confirm still checks amount/type/category,
  dedupe, status and idempotency;
- transfer suggestion never affects profit and cannot bypass account selection;
- remember-rule confirmation is atomic with ledger posting and rolls back rule
  failure;
- undo restores correct review state/provenance;
- Chat creates the same workspace-scoped suggestion rule and commits once;
- Category archive blocker, Property archive policy and rule links remain valid.

## API contract tests

For every endpoint:

- unauthenticated `401` JSON, never login redirect;
- viewer read allowed and mutation `403`;
- CSRF required for unsafe request;
- foreign/missing rule `404` without existence leak;
- request validation and stable `422` field errors;
- stale/wrong lifecycle/delete `409`;
- response Pydantic schema/camelCase/OpenAPI contract;
- Decimal amount bounds serialized as strings;
- no ORM, storage/private raw payload or HTML response;
- smallest truthful committed mutation snapshot;
- legacy `/rules*` operations disappear from generated OpenAPI after cleanup.

## React API adapter tests

- runtime schema accepts representative directory/mutation responses;
- malformed payload stays outside component state;
- discriminated handling of success/401/403/404/409/422/network/5xx;
- CSRF, JSON headers and Idempotency-Key;
- generated type drift check;
- Decimal strings are never converted to binary float for request mapping.

## React component/interaction tests

Directory:

- URL normalization and deterministic URLs;
- search/category/status/page/page size and Back/Forward;
- counts from server, filtered/primary empty states;
- viewer read-only notice/no actions;
- category query and rule hash target;
- desktop table/mobile list semantic equivalence.

Create/seed:

- panel focus, visible labels and preview;
- validation summary/inline errors/first-invalid focus;
- pending prevents double submit;
- draft preserved on expected failure;
- unsaved close confirmation and focus return;
- new rule anchor/Toast;
- seed confirmation, summary and no competing primary CTA.

Edit/lifecycle/delete:

- one row editor, unsaved switch confirmation and focus return;
- current archived target remains visible/preserved;
- stale reload/retry;
- explicit enable/disable copy and row movement;
- server capability, not client count, controls delete;
- delete dialog focus/order, pending/error/success/page normalization;
- Toast uses polite live region and does not steal focus.

Accessibility:

- keyboard-only open/edit/close/filter/pagination/action overflow/dialog;
- `aria-expanded`, `aria-controls`, selected/current states;
- table headers/caption and mobile list landmarks;
- status/mode independent of color;
- hit areas around 44px;
- reduced motion.

## Browser scenarios

Run authenticated production-shaped Playwright in Mocha and Latte at:

```text
1440 × 1000
920 × 900
390 × 844
```

Scenario A — directory and URL:

```text
open /app/rules
-> search
-> category filter
-> status tab
-> page change
-> Back/Forward/reload
-> direct #rule anchor from Category detail
```

Scenario B — create/edit/conflict:

```text
create rule
-> inspect anchor/Toast
-> edit
-> simulate stale snapshot
-> reload and retry
```

Scenario C — lifecycle/delete:

```text
disable referenced rule
-> delete blocked
-> create unused rule
-> disable
-> delete with confirmation
```

Scenario D — Import Review:

```text
import sanitized fixture
-> rule suggestion visible
-> apply rules
-> auto-apply still requires confirm
-> confirm with remembered rule
-> sibling rows update
-> open canonical Rules link
```

Scenario E — seed defaults:

```text
seed once
-> truthful counts
-> seed again
-> zero new rules and no existing mode/state changes
```

For every page/scenario: no horizontal overflow, console/page/request errors,
broken focus, hidden sticky content or theme geometry differences.

## Commands at implementation completion

### Slice 2 evidence — 2026-08-02

- focused Transaction Rules backend: `59 passed`, PostgreSQL contracts:
  `4 passed`;
- full backend: `718 passed, 5 skipped` (PostgreSQL-only cases отдельно
  прошли на временной актуальной схеме);
- frontend: `59` files, `373` tests, API drift/type/lint/styles и production
  SPA build passed;
- directory geometry: `9/9` at 1440/920/390 across Mocha/Latte/test;
- non-mutating create drawer/dirty-close/seed confirmation interaction audit:
  `3/3` at 1440/920/390.

Temporary PostgreSQL database was removed after the focused run.

### Slice 3 evidence — 2026-08-02

- API/domain focused edit contracts: `18 passed`;
- React Transaction Rules adapter/component tests: `18 passed`, включая stale
  reload, archived target preservation, single editor и dirty switch;
- full frontend: `59` files, `377` tests, formatting, lint, styles, generated
  API drift, typecheck и production SPA build passed;
- full backend Ruff и ty passed; полный pytest результат записывается после
  завершения текущего прогона;
- Slice 2 browser geometry/interaction baseline остаётся действующим; отдельный
  realistic edit/conflict browser сценарий остаётся обязательным до Slice 6
  replacement gate.

### Slice 4 evidence — 2026-08-02

- focused lifecycle API/domain contracts: `20 passed`;
- React Transaction Rules adapter/component suite: `23 passed`, включая
  authoritative impact, stale refresh/retry, blocker guidance и status-view row
  movement;
- full frontend: `59` files, `382 passed`; production SPA build passed;
- Ruff, ty, TypeScript, ESLint, styles и generated API drift passed;
- новый PostgreSQL lifecycle provenance contract: `1 passed`; весь файл дал
  `4 passed, 1 failed` на существующей `booker_tee_reparse_test`, потому что эта
  старая test DB не содержит принятого в Slice 0 restrictive rule-provenance FK
  (падение существующего delete-guard test, не lifecycle test).

### Slice 5 evidence — 2026-08-02

- focused API/application/Transaction Rules suite: `66 passed, 5 skipped`;
  PostgreSQL-only suite отдельно прошёл `5 passed` на базе с Alembic
  `20260802_0021`, включая restrictive FK и сохранение provenance;
- React Transaction Rules adapter/component suite: `25 passed`, включая stale
  reload+explicit retry, dangerous overflow, Cancel focus, blocker guidance,
  counts и last-page normalization;
- full frontend: `59` files, `387 passed`; formatting, ESLint, styles,
  generated OpenAPI drift, TypeScript и production SPA build passed;
- первый full Vitest прогон дал один timing failure в существующем
  `manual-operation-edit` URL assertion; изолированный повтор `7 passed`, затем
  полный повтор `387 passed` без изменений кода;
- Ruff и ty passed. Отдельная пустая PostgreSQL база не смогла мигрировать с
  нуля из-за существующей migration `20260722_0017` (PostgreSQL enum value и
  partial index в одной transaction); временная база удалена, Slice 5 contracts
  проверены на актуальной выделенной test schema.

## Commands at migration completion

Backend, proportionate focused tests first, then:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

Frontend:

```bash
cd frontend
npm run check
npm run build
```

Run the updated realistic/browser audit separately and record exact commands,
theme/viewports, pass counts and any intentional visual differences.
