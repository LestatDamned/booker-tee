# Slice 07: Cutover и Cleanup

Статус: completed.

## Результат

React становится canonical import-review route только после того, как realistic
document можно полностью проверить с parity по поведению, безопасности,
accessibility и responsive. Legacy остается доступным на observation gate.

## Replacement matrix

До удаления каждый сохраняемый product contract связывается с authoritative
tests:

- source traceability и validation/control totals;
- queue identity/progress и stable working context;
- classification/category/property и rule suggestions;
- transfer/raw-row/existing-operation matching;
- duplicate/lifecycle/undo;
- confirm/post/idempotency и sibling consistency;
- workspace, readonly, session expiry, `409`/`422`, draft/focus/network behavior;
- desktop, 920 px, mobile, keyboard и performance на realistic statement.

Assertions про Jinja templates, HTMX headers, OOB fragments, Alpine state,
Presenter action URLs и legacy CSS selectors являются implementation details, а
не product contracts.

## Go/no-go и dependency record

- Ответить с evidence на каждый architecture question из umbrella Stage 06.
- Записать, хватило ли loader/feature-local reconciliation. Cache/state library
  требует отдельного ADR с наблюдаемой проблемой, которую она решает.
- Сравнить query count, response size, interaction latency, test readability и
  implementation ownership с legacy path.
- Если workflow не стал проще или хотя бы локальнее и надежнее, остановить
  migration, пока legacy работает, и записать конкретную no-go причину.

## Порядок cutover

1. Пройти realistic API/component/E2E и financial regression gates.
2. Переключить internal navigation и canonical browser route на React.
3. Сохранить query-preserving legacy redirect на observation window.
4. Удалить legacy review routes/responses, Presenter/ViewModels, templates, CSS
   и implementation-only tests только после покрытия replacement matrix.
5. Сохранить import application/domain/repository и financial regression tests.

## Exit gate

User-visible outcome Stage 06 завершен, у legacy нет runtime consumer, cleanup
подтвержден evidence, а go/no-go решение для Stage 07 записано.

## Replacement evidence

| Контракт | Authoritative evidence после cutover |
| --- | --- |
| source, validation, totals, queue | application/read-model, API и React tests |
| classification, references, rules | domain/application tests, typed draft API, apply-rules component/API tests |
| transfer и matching | application/API/component tests и realistic browser panel |
| duplicate и lifecycle | pure transition policy, command/API/component tests |
| confirm, idempotency, consistency, undo | confirmation/ledger/API/component tests и browser confirm → undo capability |
| workspace, readonly, session, `409`/`422` | API и React state tests |
| responsive, focus, overflow | Playwright 1440/920/390 px, 51/51 pages |

Financial regression tests остаются в domain/application/ledger. Удалены только
assertions про Jinja, HTMX/OOB, Presenter action URLs и legacy selectors.

## Go/no-go и architecture answers

Решение: **Go**.

1. React Router client loader и feature-local state достаточны. Server snapshot
   заменяется только после successful mutation.
2. Cache library не нужна: sibling/cross-document invalidation выражена typed
   mutation response. Нового ADR нет.
3. Smallest truthful boundary — полный snapshot каждого затронутого document;
   transfer может вернуть несколько documents.
4. Classification/transfer draft живёт у строки и сохраняется при panel toggle и
   network error; committed financial state draft не становится.
5. API не повторяет Presenter: он не содержит labels, tones, placements, HTML,
   action URLs или component regions.
6. TypeScript переводит server reason/status codes в copy, но не вычисляет
   financial capability, lifecycle transition или dedupe policy.
7. Workflow локальнее HTMX/OOB: одна typed state-модель, action-specific commands
   и committed reconciliation вместо HTML fragment coordination.

Обнаруженный N+1 в transfer suggestions устранён batch queries до Go. Подробные
числа и browser gate: [`MEASUREMENTS.md`](MEASUREMENTS.md).

## Cutover и cleanup record

- canonical route: `/app/imports/documents/{document_id}/review`;
- historical `GET /imports/documents/{document_id}/review` — временный
  query-preserving `307` redirect, принадлежащий React adapter;
- mapping, import index/detail, dashboard, reports, account traceability и chat
  links сразу ведут на canonical route и сохраняют `#raw-{item_id}`;
- удалены legacy review router/responses/form parser, `page_data.py`, весь
  `presentation/review/`, 16 Jinja templates/partials, scroll JS, exclusive CSS
  и implementation-only template/presentation tests;
- `application/review/actions.py` сохранён: это не legacy presentation, его
  используют Telegram review use cases;
- apply-rules закрыт отдельной application command boundary и typed React API до
  удаления legacy;
- OpenAPI больше не публикует legacy HTML endpoints.

Completed: 2026-07-22.

Checks run: полный backend/frontend quality suite, production build, Alembic
head/offline SQL и Playwright `review_interactions` 51/51.

Intentional deviations: historical redirect и временный `/app` prefix остаются
до whole-application routing cleanup Stage 07.
