# Slice 05: Lifecycle and delete

Статус: `planned`; blocked until D2, D3 and D5 are accepted.

## Outcome

Writer archives/restores custom category with explicit impact and can
irreversibly delete only an unused archived category. Server owns every
capability and blocker.

## Server

- archive/restore endpoints with expected status/updatedAt;
- enforce accepted active-rule policy D2;
- lifecycle response states history preserved, picker availability and rule
  impact;
- full delete dependency query over all Operation statuses, Rules,
  RawTransaction suggestions and child categories;
- `DELETE /api/v1/categories/{id}` only for archived custom category with zero
  blockers and stale token;
- no cascade/nulling of historical financial/import evidence;
- auth/CSRF/isolation/404/409/422/FK integration tests.

## React

- `ActionStack`: Edit primary/quiet, lifecycle secondary, Delete in overflow
  only when server exposes it;
- archive `ConfirmationDialog` names picker/rule impact;
- restore is non-destructive but non-optimistic;
- delete dialog names category and irreversible nature;
- blocker notice links user to Rules/detail rather than failing generically;
- pending lock, retry/conflict refresh, Toast and deterministic navigation after
  delete.

## Exit gate

- archived category disappears from all active reference endpoints;
- accepted rule policy is tested end-to-end;
- no linked operation/raw row/rule/category can be deleted accidentally;
- system categories never expose lifecycle/delete;
- capability never inferred from visible counts in React.

