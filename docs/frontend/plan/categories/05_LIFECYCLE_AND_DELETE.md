# Slice 05: Lifecycle and delete

Статус: `completed 2026-08-01`; D2, D3 и D5 реализованы и проверены.

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

## Completion record

- API добавил archive/restore/delete commands со stable error codes,
  `expectedStatus`/`expectedUpdatedAt` и структурированными blockers;
- archive блокируется при active linked rules без скрытого изменения правил;
- delete разрешён только для archived custom category без operations любого
  status, rules, raw suggestions и child categories;
- dependency lookups остаются workspace-scoped; для raw suggestions и children
  добавлены индексы migration `20260801_0020`;
- detail использует общий `ActionStack`, `ConfirmationDialog`, `InlineNotice` и
  `Toast`: lifecycle остаётся рядом с Edit, irreversible Delete находится в
  overflow и появляется только по server capability;
- directory показывает прямые row actions «Открыть» и
  «В архив»/«Восстановить» на desktop и mobile; archive использует тот же
  confirmation, active-rule blocker и concurrency recovery, что и detail;
- stale mutation обновляет authoritative detail и предлагает явный retry;
- после delete directory открывается в `view=archived` и показывает toast;
- backend Categories/API: 61 passed; полный backend: 698 passed, 1 skipped;
- frontend lifecycle/API/page focused checks: 70 passed; production build,
  lint, styles, types, formatting и OpenAPI drift check прошли;
- authenticated realistic browser audit прошёл Mocha и Latte на
  1440×1000, 920×900 и 390×844, включая archive blocker и полный
  archive → restore → archive → delete сценарий.

Следующий этап: Slice 06 replacement gate, cutover и legacy cleanup.
