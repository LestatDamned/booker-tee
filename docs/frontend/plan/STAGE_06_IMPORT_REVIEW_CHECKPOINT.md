# Stage 06: Import Review Complexity Checkpoint

Status: active.

Индекс выполнения: [`import-review/README.md`](import-review/README.md).

Актуальный inventory поведения и аудит application boundary записаны в
[`import-review/INVENTORY.md`](import-review/INVENTORY.md). Queue/read model,
validation/control totals и classification/category/property slices завершены;
следующим идет transfer/matching. Legacy import review остается подключенным до
финального replacement gate.

## Goal

Проверить React/API architecture на самом сложном существующем browser workflow
до массовой миграции остальных экранов.

## User-Visible Outcome

Пользователь может закончить realistic import review в React: понять источник и
validation, исправить/классифицировать строку, обработать duplicate/match,
создать transfer/category/rule suggestion и подтвердить допустимый результат.

## Prerequisites

- Stage 05 completed and manual cleanup proved vertical replacement.
- Current import-review behavior inventory refreshed.
- Raw data preservation, dedupe and posting tests remain green.

## Planning Rule

Этот stage является complexity umbrella. До production implementation нужно
создать child plans в `docs/frontend/plan/import-review/` для устойчивых
workflow slices. Минимальные candidates:

```text
queue and read model
validation and control totals
classification/category/property
transfer and matching
duplicate and lifecycle
confirm/post and consistency updates
cutover and cleanup
```

Child plans не должны делить работу только по technical layers: каждый завершает
пользовательский кусок через API, state, UI и tests.

## Required Contracts

- queue position/progress and stable item identity;
- raw source traceability;
- validation/control-total problems;
- possible duplicate and matching candidates;
- category/property/transfer panels;
- rule suggestions without silent auto-confirm;
- local drafts, focus and errors;
- sibling/list/summary consistency after mutation;
- stale concurrency and idempotent confirm/post;
- readonly and workspace boundaries.

## Architecture Questions To Answer

1. Достаточны ли React Router loaders/actions и feature-local state?
2. Нужна ли server-state cache library для sibling invalidation?
3. Где проходит smallest truthful consistency boundary после mutation?
4. Какие draft states должны переживать navigation внутри review queue?
5. Не стал ли API UI-specific mirror старого Presenter?
6. Не дублируются ли financial/status rules в TypeScript?
7. Проще ли workflow читать и тестировать, чем HTMX/OOB equivalent?

Любая новая state/library abstraction принимается только после ответа на эти
вопросы и отдельного ADR.

## Learning Outcomes

- сложный state ownership и reducer/discriminated union, если доказана нужда;
- cancellation/race conditions между review items;
- cache invalidation как consistency problem, не library feature;
- optimistic UI limits для финансовых операций;
- component composition на нескольких связанных panels;
- integration/E2E test pyramid для длинного workflow.

## Checks

- upload/mapping/review/confirm realistic E2E;
- raw source remains visible and preserved;
- control-total mismatch and uncertainty require review;
- repeated confirm/import cannot double-count;
- transfer never affects profit;
- matching/duplicate states update every visible consumer;
- workspace/readonly/session expiry;
- draft/focus/network/`409`/`422` behavior;
- desktop/920/mobile, accessibility and performance;
- no legacy HTML or ViewModel reused as API schema.

## Go/No-Go Gate

Go only when:

- full real review is possible, not a read-only demo;
- financial semantics remain server-owned;
- API contracts are coherent without component placement;
- state transitions are explicit and testable;
- responsive/focus/draft behavior is at least as reliable as current UI;
- complexity is lower or more local than the SSR/HTMX/OOB equivalent;
- dependency cost and learning notes are documented.

If the gate fails, do not begin migration waves. Record the concrete failure and
choose one of: simplify state/API boundary, supersede an ADR, or stop the React
migration while current SSR still works.

Next after Go: [`Stage 07`](STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md).
