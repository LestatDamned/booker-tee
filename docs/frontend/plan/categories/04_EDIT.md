# Slice 04: Edit category

Статус: `planned`.

## Outcome

Writer edits custom name/kind/notes from detail with conflict recovery. System
category remains visibly immutable.

## Server

- `PUT /api/v1/categories/{id}` with `expectedUpdatedAt`;
- system immutability, workspace uniqueness and field errors;
- 404/409/422 stable codes;
- kind-impact facts: existing operations unchanged, picker compatibility may
  change, linked operation/rule counts;
- transaction rollback and committed detail/summary response.

## React

- `ExpansionPanel` below category identity;
- prefilled form with dirty-close protection and first-invalid focus;
- D4 confirmation when kind changes on a linked category;
- pending lock, server field errors, stale reload/retry with draft preserved;
- replace authoritative directory/detail snapshot and show Toast.

## Exit gate

- system/viewer has no mutation affordance;
- name change is reflected in Reports/consumer references after reload;
- kind change never rewrites Operation type/profit/history;
- two-editor stale scenario is covered.

