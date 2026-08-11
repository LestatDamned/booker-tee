# Unified Operations: пошаговая реализация

Статус: план принят 11 августа 2026; Stages 0–6 завершены.

Каждый шаг оставляет работающий срез. Существующий manual-ledger удаляется только
после parity; database data migration не требуется, потому что все источники уже
хранятся как `Operation`.

## Stage 0. Characterization и naming lock

1. Зафиксировать текущее поведение manual list, `targetOperation`, filters,
   pagination, create/edit/lifecycle/delete и reconciliation.
2. Инвентаризировать `bank_pdf`, `debt`, `system` read DTO и correction routes.
3. Зафиксировать labels «Операции», «Вручную», «Импорт», «Долг», «Система».
4. Подтвердить deep link `/app/operations?operation_id=<uuid>`.
5. Не переименовывать Python modules механически до работающего unified slice.

Gate: tests описывают текущие source-specific mutations; новая read model не
может случайно расширить права изменения.

### Результат Stage 0

Зафиксирован текущий baseline:

- canonical будущий deep link: `/app/operations?operation_id=<uuid>`;
- текущий manual slice: React `/app/ledger/manual`, read/write API
  `/api/v1/manual-ledger`, reader показывает только `source=manual`;
- текущий import correction: account detail читает источник и provenance, а
  `PUT /api/v1/accounts/{account_id}/operations/{operation_id}/review-fields`
  принимает только подтверждённый `bank_pdf`;
- debt operations читаются внутри `/api/v1/debts/{account_id}` как principal и
  interest records с `operation_id`; lifecycle остаётся в debt workflow;
- system operations уже видимы в account ledger и reports, но не имеют
  пользовательской mutation-команды;
- существующий `AccountDetailResponseMapper` уже определяет полезную форму
  `source`, typed `source_target` и server capabilities. Stage 1 переиспользует
  эти правила, но не связывает application reader с API mapper;
- UI labels переиспользуются из account detail: «Вручную», «Импорт», «Долг»,
  «Система»; option фильтра во множественном числе — «Долги». Заголовок
  коллекции — «Операции»;
- URL остаётся источником list state; `targetOperation` сохраняет выбранную
  строку, даже если она вне текущей страницы.

Characterization tests подтверждают обе стороны границы: manual mutation
отклоняет `bank_pdf`, imported correction отклоняет `manual`, а manual reader
маскирует отсутствующие и любые non-manual operations. Production behavior на
этом этапе не менялся.

## Stage 1. Unified application reader

1. Добавить `OperationsReader`, читающий все `Operation` внутри workspace.
2. Обобщить существующие filters/page и target operation lookup.
3. Добавить source, typed provenance и server-owned capabilities.
4. Batch-resolve document/debt references без N+1.
5. Сохранить current money/transfer presentation policies.
6. Не использовать activity events как financial source of truth.

Gate: manual/import/debt/system видимы в одной typed projection; foreign target
masked; query count bounded.

### Результат Stage 1

- `OperationsReader.list/get` читает workspace-scoped `Operation` всех четырёх
  sources и возвращает единый immutable DTO;
- существующая money/account presentation переиспользована без второго набора
  финансовых правил;
- общий filter contract добавил `source`, сохранив совместимость manual API;
- import/debt/system provenance представлен безопасным discriminated union без
  raw payload, storage key и произвольного metadata;
- capabilities вычисляются на backend из permission, source и status: manual и
  imported workflows остаются раздельными, debt/system не получают generic edit;
- list eager-loads provenance и account data фиксированным числом запросов;
- отсутствующий или foreign `operation_id` маскируется как отсутствие результата.

На этом этапе новый reader не подключён к HTTP и не меняет browser behavior.

## Stage 2. Versioned API

1. Добавить `GET /api/v1/operations` поверх `OperationsReader`.
2. Поддержать `operation_id`, search, type, source и текущую pagination.
3. Возвращать `targetOperation`, если deep-linked row вне текущей page.
4. Добавить auth/schema/error/isolation tests.
5. Перегенерировать OpenAPI TypeScript contracts.
6. Не удалять `/api/v1/manual-ledger` до React parity.

Gate: unified endpoint read-only относительно ledger и не раскрывает foreign
workspace operation/provenance.

### Результат Stage 2

- добавлен read-only `GET /api/v1/operations` поверх `OperationsReader`;
- endpoint поддерживает period, search, type, source, status, account, category,
  property, pagination и `operation_id`;
- invalid optional query values нормализуются tolerant-правилами существующего
  ledger list, reversed period возвращает typed `400 invalid_date_range`;
- `targetOperation` загружается отдельным workspace-scoped lookup и остаётся
  `null` для отсутствующего или foreign UUID;
- response содержит typed provenance, server capabilities, reference/source
  options и decimal money как строку;
- `/api/v1/manual-ledger` сохранён для React parity, mutation routes не
  переносились и не расширялись;
- OpenAPI и generated TypeScript contract обновлены.

Новый endpoint пока не имеет browser consumer; это gate следующего этапа.

## Stage 3. Canonical React collection

1. Добавить `/app/operations` на существующей workbench foundation.
2. Переиспользовать search, filters, pagination, rows и reconciliation.
3. Показать все sources с вторичной текстовой меткой.
4. Оставить type tabs главной классификацией; source убрать в дополнительные
   filters.
5. Реализовать empty/loading/error/retry и responsive layout 1440/920/390.
6. Сохранить одну primary CTA «Добавить операцию».

Gate: пользователь находит manual/imported operation одним поиском; URL полностью
восстанавливает list state.

### Результат Stage 3

- добавлен canonical React route `/app/operations` и navigation label
  «Операции»; старый `/app/ledger/manual` пока сохранён для parity;
- новый runtime-validated API client использует generated OpenAPI types;
- существующий collection workbench переиспользован в `scope="all"` без второго
  layout, global store, CSS foundation или финансовой presentation policy;
- rows показывают текстовые labels «Вручную», «Импорт», «Долг», «Система»;
- type tabs «Все / Доходы / Расходы / Переводы» остаются основной
  классификацией, source находится в дополнительных filters;
- search, period, references, source, page size, pagination и `operation_id`
  принадлежат URL; target вне текущей page остаётся видимым;
- одна CTA «Добавить операцию» продолжает manual create workflow;
- imported/debt/system rows на этом этапе read-only: imported `can_edit` не
  может ошибочно открыть manual mutation;
- route использует существующие loading/navigation, empty, filtered-empty,
  unauthenticated и recoverable error patterns;
- responsive geometry и accessibility остаются во владении UI foundation;
  новых raw colors, fonts и motion dependencies нет.

Source-aware selected panel и non-manual actions остаются Stage 4.

## Stage 4. Selected operation и source-aware actions

1. Открывать `operation_id` в одном `ExpansionPanel` и управлять focus/scroll.
2. Показывать typed provenance и canonical links на import document или debt.
3. Оставить manual mutation components только при соответствующих capabilities.
4. Подключить imported correction workflow через `edit_kind=imported`.
5. Debt/system operations отображать read-only с понятным recovery/navigation.
6. Не dispatch-ить mutation по одному client-side `source`; server повторно
   проверяет policy.

Gate: ни один non-manual source нельзя изменить manual-командой; deep link
работает при reload и Back/Forward.

### Результат Stage 4

- `operation_id` раскрывает ровно один `ExpansionPanel` под выбранной строкой;
  heading получает программный focus, а target вне текущей page по-прежнему
  возвращается отдельной строкой;
- UI строит canonical переходы только из typed provenance: import ведёт к raw row
  review или документу, debt — к карточке долга, отсутствующий import provenance —
  к списку импортов;
- manual edit/lifecycle/delete остаются подключены только к manual command API;
  выбор формы редактирования использует server-owned `edit_kind`;
- confirmed `bank_pdf` исправляет только description/category/property через
  существующий workspace-scoped imported correction endpoint с optimistic
  version check; сумма, дата и проводки не редактируются;
- debt и system показываются read-only с понятной причиной и, где возможно,
  переходом в owning workflow;
- существующая correction form обобщена до минимального operation subject;
  отдельная форма, mutation endpoint, detail route или client permission policy
  не добавлялись;
- во время открытой формы остальные selection links скрыты, поэтому в workbench
  не появляется вторая раскрытая панель и draft нельзя закрыть соседним действием.

## Stage 5. Cross-feature links

1. Направить workspace activity entity `operation` на unified deep link.
2. Направить links из account ledger, reports и debt history на тот же route там,
   где это улучшает workflow.
3. После import confirmation предлагать переход к созданной operation без
   автоматического выхода пользователя из review queue.
4. Не создавать backend-generated React href.

Gate: все ссылки на одну Operation используют один canonical frontend builder и
повторную workspace authorization на read endpoint.

### Результат Stage 5

- добавлен один pure frontend builder `operationHref(operationId)`; backend не
  возвращает React routes и не получает presentation responsibility;
- доступная operation entity в workspace activity ведёт на unified selected
  operation, а недоступная по-прежнему остаётся некликабельной;
- manual account movement, correctable report item и результат manual create
  больше не ведут в `/ledger/manual` или промежуточную карточку счёта;
- account ledger сохраняет primary provenance action для import/debt, а canonical
  operation link помещает во вторичное overflow-действие; system movement получает
  прямой переход к операции;
- debt payment history отдельно связывает principal и interest с созданными
  operations, не смешивая их в одну фиктивную запись;
- confirmed Import Review row предлагает явный переход «Открыть операцию», но не
  покидает review queue автоматически;
- все operation links используют `/app/operations?operation_id=<uuid>` после
  применения React Router basename и повторную workspace authorization unified
  reader при открытии.

## Stage 6. Cutover и cleanup

1. Проверить navigation label «Операции» (переименован на Stage 3).
2. Сделать `/app/operations` canonical route.
3. Добавить query-preserving redirect `/app/ledger/manual`.
4. После API/React parity удалить старый manual-only list route, schemas и tests,
   но сохранить source-specific application mutation services.
5. Обновить feature README, product docs и authenticated browser fixtures.
6. Выполнить full backend/frontend/build и browser audit.

Gate: один browser list и один read API являются canonical; parallel permanent UI
и два расходящихся read models отсутствуют.

### Результат Stage 6

- `/app/operations` — единственный browser list и `GET /api/v1/operations` —
  единственный list read API;
- `/app/ledger/manual` выполняет client-side query-preserving redirect, а
  исторический `/ledger/manual` сразу перенаправляет на `/app/operations`;
- Dashboard больше не создаёт ссылок на старый маршрут;
- удалены manual-only route loader, frontend list fetch/validation, backend GET
  endpoint, list response schemas, query adapter, repository methods и их тесты;
- manual create/edit/cancel/restore/delete endpoints и source-specific
  `ManualOperationService` сохранены: cutover чтения не ослабил mutation policy;
- общий workbench теперь принимает только canonical `OperationsListApiResponse`;
  manual form options продолжают приходить из защищённого edit contract;
- OpenAPI contract, feature README и архитектурные документы обновлены;
  database migration не потребовалась.

### Regression gate 11 августа 2026

- cross-feature frontend regression проверяет переходы между operations,
  import review, workspace activity, accounts, reports и debts;
- deep link на import row сохраняет hash, раскрывает строки за пределами первых
  50 записей и переводит focus к целевой строке после восстановления scroll;
- unified operations API и reader повторно проверены на typed provenance,
  capabilities, target lookup и workspace isolation;
- production frontend build проходит; отдельный browser-E2E стек ради этого gate
  не добавлялся.

## Test matrix

Backend:

- manual/import/debt/system list visibility;
- workspace isolation обычного и target lookup;
- confirmed/ignored/draft balance semantics не меняются;
- source-specific capabilities и mutation rejection;
- provenance allowlist;
- bounded query count и pagination stability.

Frontend:

- общий search по разным sources;
- URL filters/page/operation deep link;
- selected operation вне текущей page;
- source label не является единственным цветовым сигналом;
- manual/imported/debt/system actions;
- unavailable provenance;
- empty/loading/error/retry/pending;
- keyboard focus и mobile overflow.

Integration:

- Import Review confirmation → Operation → unified list;
- activity event → selected operation;
- debt payment → operation → debt detail;
- old manual URL сохраняет query при redirect.

## Намеренно отложено

- `/app/operations/:operationId` до доказанной сложности detail workflow;
- новый composite index до PostgreSQL EXPLAIN на representative volume;
- bulk actions, export и advanced search;
- generic operation mutation service;
- realtime и global client cache.
