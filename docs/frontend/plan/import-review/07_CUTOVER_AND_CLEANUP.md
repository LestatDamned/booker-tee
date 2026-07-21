# Slice 07: Cutover и Cleanup

Статус: planned.

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
