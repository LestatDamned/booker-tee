# Slice 05 — Cutover and cleanup

Статус: completed 2026-08-01.

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

Completed: 2026-08-01.

Implemented:

- canonical AppShell и legacy base navigation ведут в React Properties;
- `GET /properties?...` сохраняет query и отвечает `307` на
  `/app/properties?...`;
- legacy POST collection отвечает `405`, удалённые identity/lifecycle paths —
  `404`, без второго mutation stack;
- UI audit считает `/app/properties` canonical page, а `/properties` — redirect
  scenario.

Checks run:

- Ruff format/check и `ty check`;
- full backend suite: `661 passed, 1 skipped` (PostgreSQL-only concurrency test
  без `BOOKER_TEE_TEST_DATABASE_URL`); отдельно `261` Properties/API/redirect и
  named consumer regression tests;
- frontend format, lint, styles, OpenAPI freshness, typecheck и `305` tests;
- production build;
- realistic Playwright audit canonical и redirect paths в Mocha/Latte на
  `1440×1000`, `920×900`, `390×844`: 12/12 pages, без console/request/page,
  UX и horizontal-overflow errors.

Cleanup performed:

- удалены legacy Properties router, Jinja presenter/ViewModels, template и
  SSR-only tests;
- удалены property-only global CSS selectors и shared JS recent hooks;
- generated OpenAPI schema очищена от legacy HTML/form operations;
- consumer search оставил только versioned API, React feature и compatibility
  redirect/tests.

Measurements/risks:

- cleanup: `1367` удалённых строк до documentation updates, включая `754`
  строки выделенного SSR router/presentation/template/test stack;
- Properties route chunk: `24.94 kB`, gzip `7.94 kB`; CSS: `1.82 kB`, gzip
  `0.69 kB`;
- `inactive` PostgreSQL enum label остаётся намеренным техническим артефактом
  решения D1; runtime lifecycle остаётся `active | archived`.

Intentional deviations: shared Property model/repository/service и consumers
Manual Ledger, Import Review, Accounts, Reports, Transaction Rules и Chat
сохранены как domain/application dependencies, а не presentation legacy.
