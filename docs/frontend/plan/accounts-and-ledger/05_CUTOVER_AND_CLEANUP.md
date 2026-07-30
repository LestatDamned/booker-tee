# Slice 05: Accounts Cutover And Cleanup

Статус: planned.

## Outcome

React становится единственным Accounts presentation stack. Все product links
ведут в него, historical GET сохраняют совместимость, legacy HTML mutations и
account presentation удалены.

## Canonical link migration

Обновить:

- React `AppShell`;
- Import Upload no-account link;
- authenticated home;
- dashboard summary и account rows;
- reports account links;
- onboarding checklist;
- workspace/auth return paths;
- tests/fixtures;
- `scripts/ui_audit.py`.

Canonical targets:

```text
/app/accounts
/app/accounts/{account_id}
```

## Redirect policy

Оставить query-preserving GET redirects:

```text
/accounts
/accounts/{account_id}
```

Все historical account POST и HTMX GET endpoints удаляются. Redirects
принадлежат общему React compatibility adapter, а не сохраняют legacy router.

## Consumer/delete verification

Выполнить consumer search для:

```text
src/app/features/accounts/router.py
src/app/features/accounts/presentation
src/app/templates/accounts
/accounts
account-detail*
account-movement*
account-create*
account-settings*
HTMX / HX-Request / hx-*
Alpine / x-data
```

Удалить replacement-only:

- legacy router/presenter/ViewModels/templates;
- account template/presenter tests;
- account-specific legacy CSS;
- HTML operations из OpenAPI-generated TypeScript;
- legacy UI audit selectors/scenarios.

Сохранить models/repository/application/domain и financial tests. Shared legacy
selectors остаются только с конкретным SSR consumer.

## Replacement test manifest

Backend:

- полный `/api/v1/accounts` contract suite;
- auth/workspace/permission matrix;
- balance and transfer invariants;
- list aggregate performance/query characterization;
- filter/pagination/source facts;
- create/update/archive/restore concurrency;
- imported correction/version/association;
- historical redirects и отсутствие legacy mutations.

Frontend:

- format/lint/typecheck/tests/build;
- runtime schema parsing и route loaders;
- URL filters, pagination, reload and Back/Forward;
- create/settings/correction drafts;
- validation/conflict/network recovery;
- keyboard/focus/accessibility;
- responsive list/detail.

Browser:

1. empty accounts -> create;
2. second account -> manual transfer -> both details;
3. import -> confirmed row -> account detail -> source review;
4. imported correction;
5. account settings -> archive -> restore;
6. viewer readonly flow;
7. filters, pagination, deep link and historical redirects;
8. `1440×1000`, `920×900`, `390×844`;
9. no page overflow, console/page errors or failed requests.

## Documentation updates

После gate:

- свернуть этот child stage в completion record
  `docs/frontend/plan/README.md`;
- обновить `REACT_FRONTEND_DESIGN.md` current canonical routes;
- отметить account projection/legacy cleanup в ledger refactoring plan;
- удалить детальные completed slice documents по active documentation policy;
- выбрать следующий Stage 07 workflow: reports.

## Exit gate

- React — единственный Accounts UI;
- FastAPI JSON API — единственная account mutation surface;
- account security/financial policy осталась server-owned;
- historical GET только redirects;
- legacy account presentation и replacement-only tests удалены;
- full relevant backend/frontend/browser checks пройдены;
- каждый оставшийся `/accounts` consumer намеренно canonical или compatibility.
