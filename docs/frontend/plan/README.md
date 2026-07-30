# React Frontend Implementation Plan

Статус: active execution index.

Этот каталог содержит только текущую миграцию. Детальные completed stage plans
удалены; их результат зафиксирован ниже, а implementation history остаётся в
Git и коде.

## Current position

```text
Stages 0–6 completed
Stage 7 active
Imports implementation completed; full Playwright audit pending
Next prepared workflow: accounts and account ledger
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
- server application/domain tests.

## Current stage

[`STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md`](STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md)
мигрирует остальные authenticated workflows и удаляет второй presentation
stack.

Child stages:

- [`Import documents and mapping`](import-documents-and-mapping/README.md) —
  implementation completed, final browser validation pending;
- [`Accounts and account ledger`](accounts-and-ledger/README.md) — next.

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
