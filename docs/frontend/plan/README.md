# React Frontend Implementation Plan

Статус: active execution index.

Этот каталог содержит только текущую миграцию. Детальные completed stage plans
удалены; их результат зафиксирован ниже, а implementation history остаётся в
Git и коде.

## Current position

```text
Stages 0–6 completed
Stage 7 active
Imports completed
Accounts and account ledger completed
Reports completed; canonical UI is React
```

## Completed outcomes

| Stage | Outcome                                                                     |
| ----- | --------------------------------------------------------------------------- |
| 0     | React SPA, versioned API, CSS/themes и learning decisions приняты в ADR     |
| 1     | React build и safe session/API foundation работают                          |
| 2     | Semantic tokens, themes и shared UI foundation проверены                    |
| 3–5   | Manual Ledger полностью работает в React; legacy mutation UI удалён         |
| 6     | Import Review полностью работает в React; legacy review presentation удалён |

Подробные контракты завершённых features находятся рядом с кодом:

- `frontend/app/features/manual-ledger/README.md`;
- `frontend/app/features/import-review/README.md`;
- `frontend/app/features/accounts/README.md`;
- server application/domain tests.

## Current stage

[`STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md`](STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md)
мигрирует остальные authenticated workflows и удаляет второй presentation
stack.

Child stages:

- [`Import documents and mapping`](import-documents-and-mapping/README.md) —
  completed;
- Accounts and account ledger — completed 2026-07-31;
- [`Reports`](reports/README.md) — completed 2026-07-31;
- [`Properties`](properties/README.md) — active; directory/read/create
  completed, Slice 03 edit next.

### Reports completion record

Completed: 2026-07-31

Implemented:

- currency-safe Reports API and React overview, breakdowns and bounded
  uncategorized operations;
- URL filters, sorting, pagination, responsive records and server-owned
  correction capabilities;
- query-preserving historical GET redirect.

Cleanup performed:

- removed legacy Reports router, Jinja presenter/ViewModels/templates, HTMX
  partial and replacement-only tests;
- switched canonical cross-feature links to React;
- removed Reports-only legacy CSS and HTML OpenAPI operation.

Named shared consumers remain: Dashboard/Chat use the legacy-named reporting
read service, Categories uses its pure summary policy, and Categories detail
uses `.report-table`.

### Accounts completion record

Completed: 2026-07-31

Implemented:

- React account directory, detail ledger, settings, lifecycle и imported
  operation correction;
- versioned Accounts API с workspace/capability/concurrency contracts;
- query-preserving historical GET redirects.

Cleanup performed:

- удалены legacy Accounts router, Jinja presenter/ViewModels/templates и их
  replacement-only tests;
- удалён account-specific legacy CSS;
- canonical dashboard/report links переключены в React;
- HTML account operation удалена из generated OpenAPI types.

Checks run:

- relevant backend Accounts/redirect/users tests;
- frontend format/lint/styles/API/type/tests/build;
- Accounts browser audit на desktop/tablet/mobile.

Intentional deviations: none.

Measurements/risks: financial/domain actors сохранены без переписывания;
временный `/app` prefix остаётся до общего Stage 7 routing cutover.

## Status rules

- `planned` — scope принят, implementation не начат;
- `next` — ближайший stage/workflow;
- `active` — production implementation идёт;
- `blocked` — exit gate требует внешнего решения;
- `completed` — outcome достигнут, cleanup и checks записаны.

Одновременно active только один global stage. Child slices могут иметь свой
статус внутри active stage.

## Execution rules

1. Workflow делится на пользовательские vertical slices.
2. Slice проходит `application/API -> state -> UI -> tests`.
3. Domain/application не переписываются ради React.
4. Legacy работает до replacement gate, но не получает новые abstractions.
5. Cleanup входит в slice.
6. Server остаётся владельцем financial/security policy.
7. Completed детальные планы удаляются после краткой записи результата здесь.

## Completion record

При завершении текущего stage оставить короткий record:

```text
Completed: YYYY-MM-DD
Implemented:
Checks run:
Intentional deviations:
Cleanup performed:
Measurements/risks:
```

Не превращать record в журнал каждого commit.
