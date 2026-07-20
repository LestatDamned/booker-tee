# Stage 05: Manual Ledger Cutover And Cleanup

Status: active.

## Goal

Сделать React единственной authenticated manual-ledger presentation и доказать,
что vertical migration уменьшает repository, а не создает третью постоянную UI.

## User-Visible Outcome

Canonical navigation ведет на React manual ledger. Все обязательные scenarios
работают после refresh/direct link, а rollback остается ограниченным observation
window, не постоянной альтернативой.

## Prerequisites

- Stage 04 completed.
- Replacement test manifest сопоставлен с current и Frontend Next tests.
- Owner accepts documented intentional geometry/behavior differences.

## Scope

- run full manual browser matrix and performance comparison;
- switch canonical navigation/route;
- define short observation window and rollback condition;
- remove current SSR manual routes/presenters/templates;
- remove `src/app/web/features/ledger/manual/` and Next manual assets;
- remove manual-only HTMX/Alpine/JavaScript hooks and CSS selectors;
- replace/delete SSR implementation tests according to manifest;
- remove manual branches/selectors from `scripts/ui_audit.py`;
- search imports, URLs, selectors, template names and dead documentation links;
- simplify remaining ledger router by responsibility after deletion.

## Ordered Slices

1. Freeze the replacement coverage matrix.
2. Run functional, security, accessibility, responsive and performance gates.
3. Switch canonical link/route with explicit rollback condition.
4. Observe realistic use without adding compatibility abstraction.
5. Delete Frontend Next manual presentation and tests.
6. Delete current SSR manual presentation and tests.
7. Remove CSS/JS/selectors and split leftover router only if responsibility
   becomes clearer.
8. Run consumer search and full relevant regression suite.

## Cleanup Gate

Before deleting each target, prove:

- no chat/integration consumer imports browser presentation;
- replacement API/React test exists for retained product behavior;
- workspace and financial tests remain backend-owned;
- canonical URL and saved/deep links have an intentional redirect or mapping;
- no asset selector is shared by an unmigrated workflow.

## Learning Outcomes

- feature flag/rollback window versus permanent dual implementation;
- dead-code consumer search;
- characterization test versus product contract test;
- why deletion is part of architecture;
- bundle/build impact and browser caching basics.

## Checks

- backend domain/application/API relevant suites;
- frontend format/lint/type/test/build;
- full manual E2E for writer and readonly;
- desktop/920/mobile screenshots;
- direct link, refresh, back/forward and session expiry;
- query count/response size comparison;
- `rg` for deleted routes, presenters, templates, selectors and imports;
- `git diff --check`.

## Out Of Scope

- deletion of shared legacy assets still used by other workflows;
- migration of account ledger;
- final removal of all HTMX/Alpine/Jinja;
- unrelated cleanup in ledger domain/application code.

## Exit Gate

- only React serves authenticated manual ledger;
- both SSR manual implementations and their exclusive assets are deleted;
- no financial/application behavior was lost;
- repository has fewer manual presentation paths than before the pilot;
- cleanup record lists what remains and its actual consumer.

Next: [`Stage 06`](STAGE_06_IMPORT_REVIEW_CHECKPOINT.md).

## Progress

Completed slices:

- replacement coverage and deletion policy frozen in
  [`STAGE_05_MANUAL_LEDGER_REPLACEMENT_MATRIX.md`](STAGE_05_MANUAL_LEDGER_REPLACEMENT_MATRIX.md);
- canonical URL policy fixed as `/app/ledger/manual` with a query-preserving
  redirect from the historical GET URL;
- implementation-specific Jinja/HTMX/Alpine assertions separated from retained
  financial, security, API, React and browser contracts;
- readonly, missing-session, refresh and Back/Forward browser gates passed;
- response, bundle and query comparison recorded in
  [`STAGE_05_MANUAL_LEDGER_MEASUREMENTS.md`](STAGE_05_MANUAL_LEDGER_MEASUREMENTS.md);
- canonical navigation, account-detail and import-review links switched to
  `/app/ledger/manual`; historical GET preserves query through a temporary
  redirect;
- realistic browser seeding migrated from the current SSR form to React; the
  three-route transition matrix passed at desktop, 920 px and mobile widths;
- deleted the complete unconsumed `src/app/web/` runtime, `/_next` mount, manual
  templates/CSS/JavaScript, shared Next UI primitives and 55 implementation
  tests after consumer search;
- removed Frontend Next selectors/scenarios from the UI audit and regenerated
  OpenAPI TypeScript types without `/_next` HTML endpoints;
- verified the deletion with the full Python suite (`515 passed`), the complete
  frontend check (`49 passed`, lint/type/build passed), and a six-page browser
  audit of the canonical and historical URLs at desktop, tablet and mobile
  widths.

Observation/rollback condition: before SSR deletion, revert only the canonical
GET/navigation switch if React cannot complete a writer or readonly workflow,
loses saved target/filter URLs, exposes an authorization failure, or violates a
financial invariant. API/application changes are not part of that rollback.

Next slice: delete current SSR manual routes/presenter/templates/tests and their
exclusive CSS/HTMX hooks, while retaining the historical query-preserving GET
redirect to React.
