# Transaction Rules frontend contract

Transaction Rules is a canonical React workflow. It manages workspace-scoped
rules that prepare suggestions for Import Review; a rule never confirms an
operation or bypasses review, deduplication, transfer, posting or profit
invariants.

The server-side module contract, non-browser consumers and matching policies
are documented in
[`src/app/features/transaction_rules/README.md`](../../../../src/app/features/transaction_rules/README.md).

## Runtime boundary

```text
/app/rules
-> React Router route /rules
-> runtime-validated /api/v1/transaction-rules adapter
-> transaction-rules application/domain
-> workspace-scoped persistence
```

- `/app/rules` is the canonical authenticated URL.
- Historical `GET /rules?...` returns a query-preserving `307`; the browser
  keeps the `#rule-<uuid>` fragment.
- The feature does not call legacy HTML/form routes and does not own matching,
  authorization or financial policy.

## State ownership

The URL owns `q`, `category_id`, `status`, `page` and `page_size`. The route
loader owns the validated directory snapshot: records, counts, pagination,
references and server-computed capabilities.

Local feature state owns only interaction state:

- the create drawer and its draft;
- the single inline editor expanded below its record;
- pending mutations, confirmations, notices and focus return.

The server owns workspace access, target availability, lifecycle/delete
capabilities, optimistic concurrency and committed snapshots. Components must
not infer these facts from visible counts or current filters.

## Interaction contract

- Creation opens in a panel from the right side of the viewport.
- Editing expands directly below the selected desktop row or mobile record;
  only one editor can be open.
- Dirty close/switch asks for confirmation and restores focus.
- Create uses an `Idempotency-Key`; update, enable, disable and delete use the
  server timestamp snapshot and recover explicitly from `409` conflicts.
- Enable/disable changes future matching only. Existing saved suggestions are
  not silently rewritten.
- Delete is offered only for a disabled, unreferenced rule with
  server-provided `canDelete=true`, and still requires confirmation.
- Default rules are seeded only by an explicit confirmed action; seeding is
  repeat-safe and does not modify existing user rules.
- Current archived references remain visible and preservable while unavailable
  references cannot be selected as new targets.

The UI composes the shared workbench, toolbar, fields, searchable selects,
buttons, expansion and confirmation primitives. Rule records and the preview
remain feature-specific because they express matching and Import Review
semantics rather than generic CRUD.

## Required regression coverage

- API/domain: `tests/api/test_transaction_rules_api.py` and
  `tests/features/transaction_rules/`.
- React adapter/state/interactions:
  `api/transaction-rules-api.test.ts`, `transaction-rule-list-query.test.ts`,
  `transaction-rules-page.test.tsx` and the route tests.
- Cross-feature changes must retain Import Review, parser/mapping, Categories
  and Chat transaction-rule regressions.
- Browser replacement checks cover canonical and historical URLs, responsive
  geometry, keyboard/focus behavior, create/edit/lifecycle/delete and both
  themes.

Do not restore a second SSR presentation stack or move rule/financial policy
into React.
