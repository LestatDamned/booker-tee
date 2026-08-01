# Slice 05 — Cutover and cleanup

Статус: planned.

## User outcome

Properties полностью принадлежит React; canonical navigation и historical deep
links ведут в один workflow, второй mutable presentation stack удалён.

## Replacement gate до переключения

- Slices 01–04 приняты end-to-end;
- application/API tests покрывают authority, workspace isolation, validation,
  concurrency и lifecycle impact;
- React tests покрывают URL state, create/edit/lifecycle, read-only,
  pending/error/focus/draft behavior;
- realistic browser flow проходит на 1440/920/390, Mocha и Latte, без console,
  request, page и overflow errors;
- Manual Ledger, Import Review, Accounts, Reports, Rules и Chat property
  regression tests green;
- `/app/properties` production build работает same-origin с session/CSRF.

## Routing cutover

1. Добавить query-preserving `307` redirect:
   `GET /properties?... -> /app/properties?...`.
2. Не сохранять legacy POST endpoints: после cutover они должны отвечать 405/404,
   а не мутировать через второй stack.
3. Переключить React AppShell и legacy base navigation на canonical route.
4. Сохранить temporary `/app` prefix до общего Stage 7 routing decision.

Legacy `recent_property_id` не обязан становиться React URL state. Redirect
сохраняет query технически, но React безопасно игнорирует неизвестный параметр;
новый success feedback использует Toast и focused committed row.

## Cleanup

Выполнить [DELETE_MANIFEST.md](DELETE_MANIFEST.md) одним проверяемым cleanup,
перегенерировать OpenAPI types и затем провести consumer search. Не удалять
Property domain/service только потому, что рядом удаляется SSR router.

## Commands/checks

Минимальный ожидаемый набор:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
npm run format:check
npm run lint
npm run check:styles
npm run typecheck
npm test
npm run build
```

Добавить relevant Playwright property scenario и query-preserving redirect
tests. Если полный suite требует отдельной PostgreSQL database, использовать
проектный isolated test database contract.

## Completion record

После exit gate свернуть child stage в короткую запись parent index:

```text
Completed: YYYY-MM-DD
Implemented:
Checks run:
Intentional deviations:
Cleanup performed:
Measurements/risks:
```

Детальные completed plans затем удаляются согласно documentation policy;
актуальный feature contract остаётся рядом с React/application code.

