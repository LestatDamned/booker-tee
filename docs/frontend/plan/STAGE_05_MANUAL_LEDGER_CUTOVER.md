# Stage 05: Manual Ledger Cutover And Cleanup

Status: next.

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
