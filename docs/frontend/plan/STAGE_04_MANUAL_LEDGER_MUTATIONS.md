# Stage 04: Manual Ledger Mutations

Status: planned.

## Goal

Завершить manual-ledger pilot реальными financial mutations, сохранив server
authority, drafts, concurrency и понятный working context.

## User-Visible Outcome

Writer создает и редактирует income, expense и transfer, отменяет,
восстанавливает и удаляет допустимые operations. Validation/conflict errors не
стирают введенный draft. Readonly пользователь не получает mutation controls.

## Prerequisites

- Stage 03 completed.
- Existing manual application services and financial tests remain authoritative.

## Scope

### API commands

- create income/expense/transfer;
- load focused edit options/data on demand;
- update with integer `version`;
- cancel, restore and delete lifecycle commands;
- separate input schemas and common error envelope;
- `409` stale version, `422` validation, `403` readonly/permission;
- explicit idempotency audit for create and transfer.

### React interaction

- create disclosure/panel and `OperationForm` feature composition;
- lazy edit expansion under the selected row;
- explicit draft ownership and reset rules;
- field/form/server/conflict errors;
- scoped pending state without disabling unrelated rows;
- successful row/list reconciliation based on truthful consistency boundary;
- focus first invalid field and preserve working card;
- explicit destructive confirmation.

## Ordered Slices

1. Define mutation schemas and shared error mapping.
2. Implement income create end-to-end.
3. Extend the same feature contract to expense without premature form engine.
4. Add transfer with server-owned financial semantics and idempotency checks.
5. Add lazy edit data and versioned update.
6. Add cancel/restore lifecycle from capabilities.
7. Add destructive delete confirmation and reconciliation.
8. Audit drafts, focus, concurrent clicks, network failure and retry.

## Draft Contract

```text
open       -> initialize from server snapshot/defaults
type       -> local form state only
422        -> preserve draft and show field/form errors
409        -> preserve draft and offer explicit reload
cancel     -> restore last server snapshot and close
success    -> accept returned server snapshot, reconcile, close
```

No confirmed financial result is shown optimistically before server success.

## Learning Outcomes

- event handler и отличие передачи function от ее вызова;
- immutable state update;
- controlled form и validation mapping;
- async mutation lifecycle;
- closure/stale state на практическом примере;
- `AbortController`/cleanup только там, где действительно нужен;
- why React Strict Mode may expose unsafe side effects;
- server concurrency version против client draft.

## Checks

- backend command, workspace, permission, version and idempotency tests;
- income/expense affect profit correctly; transfer does not;
- component/route tests for every mutation state;
- double-submit and slow-network audit;
- `409`/`422` preserve draft;
- keyboard/focus and destructive confirmation;
- realistic E2E create/edit/cancel/restore/delete;
- no hidden mutation through GET and no HTML response in API.

## Out Of Scope

- canonical route cutover and SSR deletion;
- bulk operations;
- generic form framework;
- global mutation/cache system without demonstrated need;
- import review.

## Exit Gate

- writer completes the entire manual workflow in React;
- readonly user cannot invoke unsafe commands;
- financial and concurrency invariants are covered at backend boundary;
- frontend drafts and errors behave predictably;
- no new dependency is unexplained in ADR/handoff;
- owner can trace one mutation from event to server response and rerender.

Next: [`Stage 05`](STAGE_05_MANUAL_LEDGER_CUTOVER.md).
