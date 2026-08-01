# Slice 04: Edit category

Статус: `completed 2026-08-01`.

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

- shared `WorkbenchPanel` on the right for page-level category identity;
- prefilled form with dirty-close protection and first-invalid focus;
- D4 confirmation when kind changes on a linked category;
- pending lock, server field errors, stale reload/retry with draft preserved;
- replace authoritative directory/detail snapshot and show Toast.

## Exit gate

- system/viewer has no mutation affordance;
- name change is reflected in Reports/consumer references after reload;
- kind change never rewrites Operation type/profit/history;
- two-editor stale scenario is covered.

## Completion record

Implemented:

- `PUT /api/v1/categories/{id}` принимает normalized name/kind/notes и
  обязательный `expectedUpdatedAt`, проверяя workspace и optimistic token до
  изменения модели;
- stable `category_not_found`, `category_update_conflict`,
  `category_validation_error` и `category_system_immutable` разделяют recovery
  paths без утечки cross-workspace существования;
- detail DTO отдаёт server-owned kind options и `kindChangeImpact`: количество
  связанных операций/правил, неизменность истории, возможное изменение picker
  compatibility и необходимость confirmation;
- `WorkbenchPanel` переиспользует Category form validation, Foundation fields,
  одноколоночную side-form композицию, error summary, inline conflict notice,
  dirty-close dialog и Toast;
- при conflict актуальный detail загружается в текущем URL/filter context,
  пользовательский draft сохраняется, а повторный PUT использует свежий token;
- смена kind связанной категории требует явного confirmation; существующие
  Operation type, MoneyEntry, profit и отчётная история не переписываются;
- system category и viewer получают видимый read-only state без edit action.

Automated coverage: successful authoritative replacement, normalized API
dispatch, CSRF, duplicate/field errors, system/viewer denial, linked-kind
confirmation, first-invalid focus, dirty-close protection и two-editor stale
reload/retry.

Checks:

- focused backend Categories/API — `52 passed`; Ruff и ty — passed;
- full backend — `689 passed, 1 PostgreSQL-only skipped`;
- focused React Categories/routes/Foundation — `88 passed`; full React —
  `347 passed`;
- Prettier, ESLint, style contract, OpenAPI drift, TypeScript и production
  prerender build — passed;
- realistic Category Detail/Edit audit в Mocha и Latte на 1440/920/390 — 6/6
  passed, horizontal overflow и browser/request/UX errors отсутствуют.

Measurements: category detail main chunk `21.09 kB` (`7.16 kB` gzip), feature
CSS `3.19 kB` (`0.86 kB` gzip).

Следующий этап: Slice 05 lifecycle/delete policy и UI.
