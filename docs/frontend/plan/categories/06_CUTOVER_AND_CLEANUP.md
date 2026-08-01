# Slice 06: Cutover and cleanup

Статус: `completed 2026-08-01`.

## Outcome

React Categories становится единственным authenticated category presentation;
historical GET URLs совместимы, legacy mutable SSR удалён.

## Replacement gate

- Slices 01–05 completed and D1–D5 recorded;
- application/API/React tests cover all observed outcomes and invariants;
- Manual Ledger, Import Review, Reports, Accounts, Rules and Chat regression
  suites pass;
- Mocha/Latte browser audit at 1440/920/390 passes for directory/detail,
  read-only, mutations and Reports round trip;
- direct/deep/query/back links verified;
- delete manifest consumer search classified.

## Cutover

- AppShell and remaining legacy nav use `/app/categories`;
- Reports uses `/app/categories/:id` preserving filters/return;
- `GET /categories?...` and `GET /categories/:id?...` redirect query-preserving
  to React equivalents;
- no historical POST compatibility routes;
- run generated OpenAPI regeneration after router replacement.

## Cleanup

Execute [DELETE_MANIFEST.md](DELETE_MANIFEST.md): remove SSR router,
presenter/ViewModels, both templates, category-only global CSS/JS hooks and
replacement-only tests. Preserve domain/application code and all named
cross-feature consumers.

## Final checks

- Ruff format/check, ty and relevant/full pytest;
- frontend format/lint/styles/OpenAPI/typecheck/tests/build;
- realistic browser audit in both themes;
- final `rg` searches from delete manifest;
- update parent plan with completion date, checks, cleanup and measurements.

## Completion record

- AppShell и legacy base navigation ведут в React Categories;
- historical `GET /categories` и `GET /categories/{uuid}` выполняют
  query-preserving `307` redirect в `/app/categories*`;
- historical POST compatibility отсутствует: collection/detail возвращают
  `405`, старые archive/restore/delete paths — `404`;
- SSR router, presenter/ViewModels, templates и 15 replacement-only tests
  удалены; category-only global CSS/JS hooks также удалены;
- realistic UI fixture создаёт категории через React/API и больше не зависит от
  legacy forms;
- generated OpenAPI больше не содержит HTML `/categories*` operations;
- delete-gate search оставляет только compatibility redirects/tests,
  `/api/v1/categories`, canonical `/app/categories*`, React Router-relative
  paths и named domain consumers;
- backend: Ruff/ty passed, `683 passed, 1 skipped`; frontend full check:
  formatting/lint/styles/OpenAPI/types and `357 passed`; production build passed;
- Mocha/Latte realistic browser audit прошёл directory, dynamic detail и
  historical redirect на 1440×1000, 920×900 и 390×844: 9/9 pages per theme;
- production chunks: Categories `19.59 kB` (`6.81 kB` gzip), detail
  `27.87 kB` (`8.91 kB` gzip); CSS `2.12/3.43 kB` (`0.76/0.92 kB` gzip).
