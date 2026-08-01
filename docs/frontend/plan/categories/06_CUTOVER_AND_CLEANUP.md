# Slice 06: Cutover and cleanup

Статус: `planned`.

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

