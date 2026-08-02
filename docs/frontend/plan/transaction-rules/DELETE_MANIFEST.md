# Transaction Rules legacy delete manifest

Статус: executed 2026-08-02 после Slice 6 replacement gate и повторного
consumer search.

## Delete after replacement evidence

### SSR presentation adapter

- `src/app/features/transaction_rules/router.py`;
- `src/app/features/transaction_rules/router_forms.py`;
- `src/app/features/transaction_rules/presentation/models.py`;
- `src/app/features/transaction_rules/presentation/presenter.py`;
- `src/app/features/transaction_rules/presentation/__init__.py`;
- `src/app/templates/transaction_rules/index.html`;
- `src/app/templates/transaction_rules/_rule_form.html`;
- `src/app/templates/transaction_rules/_rule_row.html`;
- `src/app/templates/transaction_rules/_rule_edit_panel.html`;
- `src/app/templates/transaction_rules/_rule_list_panel.html`.

### SSR-only tests

- `tests/features/transaction_rules/test_transaction_rules_template.py` after
  all behavior assertions have a named application/API/React owner;
- route anchor helper assertions replaced by React URL/deep-link tests.

Do not mechanically move template string assertions into React snapshots.

### Registration and generated contract

- `transaction_rules_router` import/include in `src/app/main.py`;
- legacy `/rules*` HTML/form operations from `frontend/openapi.json` and
  `frontend/app/api/generated/schema.ts` through normal regeneration;
- old FastAPI operation body schemas belonging only to form routes.

### Rule-specific legacy CSS

Remove after selector consumer scan:

- `.rule-create-*`, `.rule-form*`, `.rule-advanced-*`;
- `.rules-page-actions`, `.rules-list-panel`, `.rule-list-*`;
- `.rule-filter-form*`, `.rule-card*`, `.rule-more-actions*`;
- old dormant `.rule-card-inactive`, `.rule-card-main`, `.rule-card-title`,
  `.rule-status` blocks;
- rule-only responsive overrides at 920/mobile breakpoints.

Keep shared `.entity-card`, `.row-drawer`, `.filter-form`, `.financial-row` and
other selectors while Workspaces/remaining SSR pages still consume them.

### Rule-specific legacy JS hooks

From `src/app/static/js/entity-target.js` remove only:

- `rule-card--recent` cleanup;
- `.rule-list-feedback` cleanup;
- `recent_rule_id` query cleanup if no other route uses it.

Keep generic working/target behavior until all remaining SSR consumers are
audited. Do not delete the whole file as part of Transaction Rules alone.

### UI audit scenario

Replace in `scripts/ui_audit.py`:

- SSR `/rules` canonical page entries;
- `details.rule-create-details`, `#new-rule`, `.rule-card__title` and other SSR
  selectors;
- rules-specific design assertions.

Add `/app/rules` React scenario plus `/rules` redirect evidence. Historical GET
redirect remains a live compatibility consumer and must not be mistaken for
the canonical page.

## Add/retarget at cutover

- React Router route `/rules` and route loader;
- AppShell item becomes `reactRoute: true`/`NavLink`;
- Import Review link `/transaction-rules` becomes canonical SPA `/rules`;
- Categories query/hash links use React navigation where in-SPA and retain
  `/rules?category_id=...` / `/rules#rule-...` semantics;
- `src/app/legacy_frontend_redirects.py` gets query-preserving GET `/rules` to
  `/app/rules`;
- API v1 router includes Transaction Rules JSON router.

Legacy POST, edit-fragment, toggle and delete paths are deleted, not redirected.

## Keep: domain/application/persistence consumers

These are not legacy presentation and must remain unless separately refactored
with consumer evidence:

- `src/app/features/transaction_rules/models.py` and enums;
- `repository.py` after extending workspace/pagination/impact queries;
- `application/commands.py` or approved Pydantic replacements;
- `application/rule_application.py`;
- `application/rule_management.py` after contract hardening;
- `application/fixture_seeding.py` after policy correction;
- `domain/matching.py`, `patterns.py`, `suggestions.py`, `text.py`;
- `errors.py` or typed successor;
- migrations `20260613_0006` and `20260613_0007`;
- Transaction Rule/Workspace and RawTransaction foreign-key relationships.

Named runtime consumers:

- known statement parser process;
- unknown statement mapping import;
- React/API Import Review apply/confirm/undo lifecycle;
- Chat review rule suggestion flow;
- Categories directory/detail/count/archive/delete policy;
- Properties reference policy;
- new Transaction Rules JSON API.

## Keep: non-replacement tests

- pure matching/normalization/suggestion tests from
  `tests/features/transaction_rules/test_transaction_rules.py`;
- Import Review classification/confirmation/lifecycle/read/API tests;
- unknown mapping/known import application tests;
- Chat review rule tests;
- Categories rule count/preview/lifecycle tests;
- ledger/report transfer/profit invariants.

Some tests may be split/renamed by owner, but must not disappear because SSR is
deleted.

## Shared assets requiring last-consumer proof

Do not delete merely because Transaction Rules used them:

- Jinja `base.html`, `ui/_action.html`, `ui/_more_actions.html`;
- HTMX/Alpine/vendor scripts;
- legacy global `app.css` as a whole;
- `entity-target.js` generic behavior;
- `app.shared.ui.actions.ActionVM`;
- Category/Property services and repositories;
- templating label helpers.

Workspaces, Users, Dashboard, Chat/admin/public/auth pages may still be named
consumers during Stage 7.

## Consumer search commands

Before deletion and again after deletion:

```bash
rg -n "TransactionRulesPagePresenter|RulesPageVM|rule_anchor_url|/rules" src tests frontend scripts
rg -n "rule-card|rule-create|rule-filter|rules-list|recent_rule_id" src tests frontend scripts
rg -n "transaction_rules.router|transaction_rules.presentation" src tests
rg -n "TransactionRule(Application|Management|Repository)?" src tests
rg -n "suggested_by_rule_id|rule_suggestion|apply_rules" src tests frontend
```

Every remaining hit must be one of:

- new React/API contract;
- query-preserving historical GET redirect;
- domain/application/persistence consumer;
- current test/documentation with an explicit owner.

Consumer proof также выявил два не перечисленных изначально SSR-only read
adapter: `application/rule_queries.py` и `listing.py`. Их единственными
runtime consumers были удалённые presenter/router; replacement-only tests были
удалены вместе с ними. SQL directory read и JSON projection остаются в
workspace-scoped repository/API.

## Final delete gate

- [x] canonical navigation and cross-feature links use React;
- [x] full replacement test manifest passes;
- [x] historical GET redirect preserves query; anchors are verified separately in
  browser because fragments are not sent to server;
- [x] no old mutation surface remains reachable;
- [x] generated OpenAPI has only JSON Transaction Rules operations;
- [x] rule-specific CSS/JS/template references are zero;
- [x] remaining shared legacy files each have a named runtime consumer;
- [x] Git diff contains no deletion of raw data, migrations or domain behavior.
