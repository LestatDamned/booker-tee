# Stage 05: Manual Ledger Replacement Matrix

Status: frozen for cutover.

Этот manifest отделяет сохраняемый продуктовый контракт Manual Ledger от
удаляемых деталей двух SSR-реализаций. Он является gate для удаления current SSR
и Frontend Next, а не списком тестов, которые нужно механически переписать.

## Canonical URL Policy

- canonical browser URL после cutover: `/app/ledger/manual`;
- старый `GET /ledger/manual` сохраняет query string и fragment через redirect на
  `/app/ledger/manual` в observation window;
- внутренние navigation links сразу указывают на canonical React URL;
- JSON API остаётся под `/api/v1/manual-ledger`;
- старые HTML mutation endpoints и `/_next/ledger/manual` не являются публичным
  compatibility contract и удаляются после replacement gate.

Fragment не отправляется HTTP server, поэтому сохранение `#operation-<id>` при
старой закладке выполняет browser: redirect меняет только pathname/query.

## Product Contract Replacement

| Contract                                                            | Legacy evidence                                  | Authoritative replacement                                                          | Gate    |
| ------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------------- | ------- |
| Workspace-scoped list, references and target                        | current baseline GET; Next listing route tests   | `test_manual_ledger_api.py`, route/page tests                                      | covered |
| Decimal money, income/expense direction and transfer outside profit | current presenter; Next presenter tests          | API semantics tests, model tests, ledger domain tests                              | covered |
| Tolerant filters, pagination and stable target URL                  | Next query-state/list/update tests               | API normalization, filter/page/route tests, browser deep link                      | covered |
| Writer versus readonly capabilities                                 | current readonly baseline; Next permission tests | API permission tests, React component test and isolated readonly browser response  | covered |
| Create income, expense and transfer                                 | Next create tests                                | versioned API tests, create component tests, realistic browser audit               | covered |
| Create replay safety                                                | absent in current SSR; partial Next behavior     | backend idempotency tests and retry component test                                 | covered |
| Lazy edit without eager forms                                       | current baseline; Next lazy edit tests           | edit component test and realistic browser audit                                    | covered |
| `422` preserves draft and focuses invalid field                     | Next local validation tests                      | create/edit component tests and browser audit                                      | covered |
| `409` preserves stale draft and reloads explicitly                  | Next update conflict tests                       | API conflict test, edit component test and desktop browser conflict                | covered |
| Cancel/restore from server capabilities                             | Next lifecycle tests                             | API, lifecycle component and browser workflow tests                                | covered |
| Destructive delete confirmation                                     | Next lifecycle delete response                   | delete component and browser workflow tests                                        | covered |
| Row-scoped pending and retry after network failure                  | absent/implicit in SSR                           | page/create/edit/lifecycle component tests                                         | covered |
| Direct navigation and refresh                                       | current/Next full HTML fallback                  | SPA fallback test and browser deep-link/reload navigation                          | covered |
| Back/forward history                                                | implicit browser behavior                        | realistic React browser audit                                                      | covered |
| Expired session                                                     | legacy auth redirect                             | route unauthenticated test and isolated browser context                            | covered |
| Responsive geometry and no horizontal overflow                      | current baseline and Next browser screenshots    | React audit at 1440, 920 and 390 px                                                | covered |
| Query/response/bundle comparison                                    | current baseline metrics                         | [`STAGE_05_MANUAL_LEDGER_MEASUREMENTS.md`](STAGE_05_MANUAL_LEDGER_MEASUREMENTS.md) | covered |

## Tests Removed With Their Implementation

These assertions have no React product value and are deleted with their owner:

- Jinja template names, partial boundaries and full-page fallback HTML;
- HTMX headers, `HX-Retarget`, `HX-Reswap`, OOB fragments and response scopes;
- Alpine disclosure source hooks and CSS class ordering;
- current/Next presenter URLs, form actions and HTML action policies;
- exact legacy wrapper classes, drawer markup and segmented-control markup;
- counts of disclosure reset markers and other DOM patch implementation details.

The financial/application tests in `tests/features/ledger/test_ledger.py` and the
JSON API tests are retained. Account detail and import review consumers retain a
browser link to an operation, but migrate the target from `/ledger/manual` to
the canonical React URL; they do not depend on either manual SSR presenter.

## Intentional Product Differences

- React owns draft/request state instead of rebuilding it in HTML fragments.
- Create is a client disclosure, not a separately fetched SSR form.
- Validation uses JSON `422`; concurrency uses JSON `409` with integer version.
- No visible UUID/debug payload and no legacy CSS/HTMX state classes.
- Filters are draft state until explicit apply; `operation_id` does not make the
  filter disclosure look active.
- The first SPA document is a small shell followed by same-origin session and
  manual-ledger API requests, not a fully rendered financial HTML response.

The retained geometry is the calm dense workbench hierarchy: date, money and
description remain primary; classification/status and actions remain secondary;
desktop, 920 px and mobile layouts preserve the established reading order.

## Cutover Gate Result

All pre-cutover gates passed. Navigation and historical GET now resolve to
`/app/ledger/manual`; realistic seeding also uses React. Frontend Next runtime,
assets and implementation tests are deleted. Current SSR manual routes,
presenter/ViewModels, templates, exclusive assets and implementation tests are
also deleted. The historical GET is now a query-preserving compatibility route
owned by the React adapter; no legacy manual mutation endpoint remains.
