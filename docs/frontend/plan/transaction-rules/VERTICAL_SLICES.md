# Transaction Rules vertical slices

Статус: approved 2026-08-02. Каждый slice идёт
`application/API -> state -> UI -> tests`. Legacy SSR остаётся рабочим до
Slice 6 replacement gate.

## Slice 0 — Contract hardening — completed 2026-08-02

User-visible outcome: none; server behavior becomes safe enough to expose as
JSON.

Server work:

- characterize current matching, suggestion and cross-consumer behavior;
- make directory read side-effect free;
- add rule validation for pattern/name/amount range;
- validate every target workspace, including dormant account;
- separate interactive create from weak seed idempotency;
- define current archived reference and re-enable policy;
- add optimistic `updated_at` guards;
- add raw-reference impact and approved delete policy;
- correct seeder promise: never mutate existing user rule.

Exit gate:

- [x] D1–D7 approved;
- [x] no React code added;
- [x] domain/application/workspace/delete/seed tests pass;
- [x] known parser, mapping, Import Review and Chat regressions pass;
- [x] PostgreSQL delete guard preserves raw provenance and workspace cascade;
- [x] full backend and frontend contract checks pass.

## Slice 1 — Read-only directory API and route

User outcome: authenticated user can open React list, search/filter/page it and
deep-link from Categories without mutation controls.

Server:

- Pydantic directory/read DTOs;
- SQL filtering, counts, ordering and bounded pagination;
- reference/current-archived projection;
- reader/viewer capabilities;
- auth, schema, isolation and no-read-side-effect tests.

React:

- `/app/rules` route/loader/runtime schema;
- Workbench composition, search, tabs, category filter, pagination;
- responsive semantic table/mobile list;
- target hash state and read-only notice;
- loading/not-found/error states.

Legacy remains canonical in navigation. Direct React route is pre-cutover
evidence only.

Exit gate:

- URLs restore state with reload/Back/Forward;
- category query/hash links work on React route;
- 1440/920/390 no overflow in all themes;
- viewer sees complete rule meaning and no mutation controls.

## Slice 2 — Create and seed defaults

User outcome: writer creates one reviewed rule or explicitly loads missing
defaults with truthful summary.

Server:

- create request/response/error/idempotency contract;
- seed defaults request and result counts;
- full target/amount/pattern validation;
- no silent reuse or mutation of existing rule.

React:

- `WorkbenchPanel` create form and condition/outcome preview;
- pending/error summary/focus/draft preservation/unsaved close confirmation;
- stable new-rule anchor and Toast;
- secondary seed confirmation, pending, summary Toast and authoritative reload.

Exit gate:

- repeat/lost-response behavior is safe;
- seeding twice creates no duplicate and changes no existing rule;
- viewer cannot invoke mutation through hidden/manual API request;
- current SSR create/seed still work until cutover.

## Slice 3 — Edit

User outcome: writer changes one rule in context and understands stale/current
archived targets.

Server:

- optimistic update contract;
- current target projection and preservation of dormant fields;
- typed field/conflict errors.

React:

- only one `ExpansionPanel` editor open;
- focus return, unsaved switch/close confirmation;
- local draft, field errors, reload-and-retry on conflict;
- committed row replacement and Toast.

Exit gate:

- two-tab stale edit is rejected;
- editing an unrelated field cannot clear a current archived target;
- update cannot attach foreign-workspace or newly unavailable target;
- list filters/page remain stable.

## Slice 4 — Enable and disable

User outcome: writer disables future matching or deliberately re-enables a
valid rule; existing review suggestions are not silently rewritten.

Server:

- explicit enable/disable commands with expected state/timestamp;
- target revalidation and blocker codes;
- authoritative summary/impact response.

React:

- direct subordinate lifecycle action through `ActionStack`;
- impact copy: future matching changes, existing suggestions remain;
- pending row lock, conflict reload/retry, Toast;
- row moves correctly between URL status views.

Exit gate:

- disable affects new parse/manual reapply but not existing snapshot until
  explicit apply;
- invalid archived target cannot be silently reactivated;
- Categories/Properties accepted policies remain intact.

## Slice 5 — Safe delete

User outcome: writer deletes only an unused disabled rule and receives clear
blocker guidance otherwise.

Server:

- workspace-scoped reference count and capability;
- disabled + zero-reference + stale token enforcement;
- typed blocker response and deleted identity;
- FK/race integration test.

React:

- Delete only in dangerous overflow group;
- `ConfirmationDialog`, initial focus Cancel, irreversible copy;
- referenced/active rule shows disable/blocker path rather than false action;
- pending, conflict recovery, Toast and page normalization.

Exit gate:

- referenced raw row never loses provenance through UI delete;
- no raw source/suggestion/operation is cascaded or rewritten;
- forged delete cannot bypass server capability.

## Slice 6 — Import Review links and replacement gate

User outcome: all canonical navigation reaches React and all rule entry points
continue to affect Import Review consistently.

Work:

- switch AppShell Rules item to React `NavLink`;
- fix Import Review `/transaction-rules` link to `/rules` within SPA;
- keep Categories category/hash links and make them React-aware;
- add query-preserving historical GET `/rules -> /app/rules`;
- run end-to-end known parser, mapping, apply, remember rule and Chat scenarios;
- run realistic browser flow and baseline comparison;
- execute [`DELETE_MANIFEST.md`](DELETE_MANIFEST.md) only after replacement
  evidence passes;
- regenerate OpenAPI so legacy HTML/form operations disappear;
- update feature/current-stage documentation and learning note.

Exit gate:

- React is the only authenticated browser mutation surface for rules;
- legacy POST paths are gone, not redirected;
- GET `/rules?...#...` behavior has accepted query/hash compatibility;
- all remaining server Transaction Rules code has named non-SSR consumers;
- full backend/frontend/browser checks pass.

## Slice 7 — Plan closure

After completed implementation:

- add a short completion record to `docs/frontend/plan/README.md`;
- update `REACT_FRONTEND_DESIGN.md` current state;
- move durable feature contract to
  `frontend/app/features/transaction-rules/README.md` and server tests;
- remove this detailed child plan according to docs retention policy once its
  only consumer is Git history.

Do not keep a permanent migration journal after cutover.
