# React Frontend Implementation Plan

Статус: active execution plan.

Этот каталог отвечает на вопрос «что реализуем следующим и по каким критериям
этап завершен».

Не дублировать здесь:

- product UX — см. [`DESIGN.md`](../../design/DESIGN.md);
- target architecture и cleanup manifest — см.
  [`REACT_FRONTEND_DESIGN.md`](../../design/REACT_FRONTEND_DESIGN.md);
- причины технических решений — см.
  [`Architecture Decision Records`](../../architecture/decisions/README.md);
- financial invariants — см. [`DOMAIN_MODEL.md`](../../domain/DOMAIN_MODEL.md).

## Current Position

```text
Stage 0  completed
Stage 1  completed
Stage 2  completed
Stage 3  next
Stage 4+ planned
```

| Stage | Status | Outcome |
| --- | --- | --- |
| [`00`](STAGE_00_DECISIONS_AND_FREEZE.md) | completed | React decision, ADR and SSR freeze are explicit |
| [`01`](STAGE_01_RUNTIME_AND_API_FOUNDATION.md) | completed | React builds, FastAPI exposes safe session/API foundation |
| [`02`](STAGE_02_VISUAL_FOUNDATION.md) | completed | Tokens, themes and shared geometry are proven |
| [`03`](STAGE_03_MANUAL_LEDGER_READ.md) | next | Manual ledger list works read-only through JSON API |
| [`04`](STAGE_04_MANUAL_LEDGER_MUTATIONS.md) | planned | Full manual create/edit/lifecycle works in React |
| [`05`](STAGE_05_MANUAL_LEDGER_CUTOVER.md) | planned | React becomes canonical; two manual SSR slices are deleted |
| [`06`](STAGE_06_IMPORT_REVIEW_CHECKPOINT.md) | planned | Complex import review validates or challenges the architecture |
| [`07`](STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md) | planned | Remaining workflows migrate and authenticated SSR is removed |

## Status Rules

- `planned` — sequence is accepted, implementation has not started;
- `next` — ближайший этап, prerequisites выполнены;
- `active` — сейчас меняется production code; одновременно только один stage;
- `blocked` — exit gate невозможно выполнить без отдельного решения;
- `completed` — все exit gates выполнены и checks реально запущены;
- `superseded` — новый plan явно заменил этот stage.

При старте этапа обновить его status и таблицу выше. Не отмечать `completed` по
проценту выполненных checklist items: важен пользовательский outcome и exit gate.

## Execution Rules

1. Один stage выполняется маленькими reviewable slices.
2. Каждый slice проходит `API/application -> frontend state -> UI -> tests`, если
   его outcome пересекает все эти границы.
3. Domain/application код не переписывается ради удобства React.
4. Legacy остается доступным до replacement gate, но не получает новые shared
   abstractions.
5. Cleanup является частью stage, а не неопределенным будущим долгом.
6. Нетривиальный TS/React concept объясняется через Python-аналогию и границы
   этой аналогии.
7. Если stage становится слишком большим, он делится на child plan до написания
   связанного production-кода; global stage sequence не меняется молча.

## Stage Completion Record

При завершении в stage-файле добавить короткий блок:

```text
Completed: YYYY-MM-DD
Implemented:
Checks run:
Intentional deviations:
Cleanup performed:
Learning notes updated:
```

Этот record фиксирует факт реализации. Git history остается источником точного
diff, поэтому stage-документ не превращается в подробный development journal.
