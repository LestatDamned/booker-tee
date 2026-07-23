# Аудит React frontend после миграции Manual Ledger и Import Review

Дата: 2026-07-23.

Область аудита:

- `frontend/app/`;
- versioned JSON API в `src/app/api/`;
- совместимость и остатки SSR для Manual Ledger и Import Review;
- frontend tests, browser-gate records и migration documents.

Метод: статический анализ фактического кода, dependency/consumer search,
проверка generated OpenAPI types и запуск полного `npm run check`. Production
код в рамках аудита не изменялся.

---

## A. Executive summary

Миграция двух страниц прошла успешно. React уже является canonical runtime для
`Manual Ledger` и `Import Review`; старые реализации этих страниц удалены, а
старые GET URL оставлены только как безопасные query-preserving redirects.
Финансовые правила, workspace authorization, lifecycle и итоговое состояние
остались на сервере.

Фактическая архитектура — **прагматичная feature-based структура с тонкими
route-модулями, feature-local API/state и небольшим shared UI foundation**. Это
не Feature-Sliced Design и не чистая layer-based архитектура. Полный переход на
FSD не нужен.

Продолжать миграцию следующих SSR-страниц можно. Перед массовой волной стоит
сделать короткий normalization slice, но блокирующих архитектурных дефектов нет.

Сильные стороны:

- React Router Framework Mode в SPA mode, route-level code splitting;
- `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`;
- типы запросов и DTO генерируются из FastAPI OpenAPI;
- network JSON дополнительно проверяется Zod;
- server state не помещён в глобальный store;
- URL владеет фильтрами, pagination и import-review view state;
- формы сохраняют draft после `422` и network errors;
- финансовые mutations не показываются optimistically;
- CSRF, same-origin cookie, workspace scope и server capabilities реализованы
  правильно;
- shared UI строится по ответственности, а не только по сходству;
- CSS Modules изолируют React от legacy global CSS;
- Catppuccin Mocha и Latte уже реализованы через semantic tokens;
- 151 frontend test и сильное backend API/domain покрытие.

Главные риски:

1. Transport/error handling повторяется и различается между features.
2. Generated types могут отстать от FastAPI: `npm run check` не проверяет
   OpenAPI drift.
3. `Import Review` сконцентрировал слишком много историй в `review-item.tsx`
   (889 строк) и одном CSS Module (1530 строк).
4. Portaled action menu неудобен для клавиатуры: после открытия focus не
   переводится в меню.
5. Import-review fields показывают ошибки, но не всегда выставляют
   `aria-invalid`.
6. Requests не принимают `AbortSignal`; request-id guards решают только часть
   race problems.
7. Style check не обнаруживает использование отсутствующего token
   `--radius-xs`.

Общая оценка:

| Область        | Оценка | Вывод                                                        |
| -------------- | ------ | ------------------------------------------------------------ |
| Архитектура    | 8/10   | проста, предсказуема, готова к росту                         |
| React          | 8/10   | корректное state ownership; мало лишних effects              |
| TypeScript     | 8/10   | строгий и полезный, но drift gate отсутствует                |
| API boundary   | 7/10   | хороший контракт, повторяется transport plumbing             |
| Формы          | 7/10   | Manual Ledger силён; Import Review менее унифицирован        |
| CSS/themes     | 8/10   | theme-ready; import stylesheet слишком велик                 |
| Accessibility  | 7/10   | хорошая база, два важных interaction gaps                    |
| Tests          | 9/10   | сильное рациональное покрытие без тестирования каждой строки |
| Legacy cleanup | 9/10   | страницы удалены безопасно; redirect нужен временно          |

**Решение: Go для Stage 07**, но сначала желательно закрыть P1–P5 из этого
отчёта.

Что важно понять Python-разработчику:

`clientLoader` похож на route-level query handler, React component — на
функцию, которая заново вычисляет UI из аргументов и локального состояния, а
`useState` хранит состояние конкретного экземпляра UI. Server snapshot здесь не
становится новой финансовой истиной: React заменяет его только ответом успешно
закоммиченной backend-команды.

---

## B. Карта frontend

```text
frontend/
├── app/
│   ├── root.tsx                         HTML shell, global CSS, root error UI
│   ├── routes.ts                        route table
│   ├── routes/
│   │   ├── manual-ledger.tsx            route adapter и route states
│   │   ├── manual-ledger-loader.ts      session + ledger parallel load
│   │   ├── import-review.tsx            route adapter и route states
│   │   └── import-review-loader.ts      session + review parallel load
│   ├── api/
│   │   ├── generated/schema.ts          generated OpenAPI TypeScript types
│   │   ├── session.ts                   session query и request-state union
│   │   └── session-schema.ts            runtime validation session DTO
│   ├── features/
│   │   ├── manual-ledger/
│   │   │   ├── api/                     queries, mutations, runtime schemas
│   │   │   ├── list/                    list, URL filters/search/pagination
│   │   │   ├── operation/               row, draft, create/edit/lifecycle/delete
│   │   │   └── manual-ledger.module.css feature stylesheet
│   │   └── import-review/
│   │       ├── api/                     queries, mutations, runtime schemas
│   │       ├── import-review-page.tsx   page snapshot/filter/queue owner
│   │       ├── review-item.tsx          row composition + presentation rules
│   │       ├── classification-panel.tsx classification/category draft
│   │       ├── transfer-panel.tsx       transfer draft and command
│   │       ├── *-actions.tsx            posting/lifecycle/rule commands
│   │       └── import-review.module.css whole feature stylesheet
│   ├── shell/
│   │   └── app-shell.tsx                authenticated layout/navigation
│   ├── ui/                              stable reusable visual responsibilities
│   ├── shared/
│   │   ├── date/                        date formatting
│   │   └── money/                       decimal-string display formatting
│   └── styles/
│       ├── tokens.css                   spacing/type/geometry/motion primitives
│       ├── foundation.css               reset, global semantics, focus/reduced motion
│       ├── shell.module.css             authenticated shell styles
│       └── themes/                      raw palettes → semantic color tokens
├── scripts/check-styles.mjs             theme/contrast/style policy checks
├── openapi.json                         generated temporary input, ignored
└── package.json                         runtime/tooling/check commands
```

### Важные файлы и ответственность

- `frontend/app/root.tsx` — создаёт HTML document, подключает global CSS и
  показывает root fallback/error.
- `frontend/app/routes.ts` — единственный список React routes.
- `frontend/app/routes/manual-ledger.tsx` — переводит loader result в
  `ManualLedgerPage` или route-level error/login state.
- `frontend/app/routes/manual-ledger-loader.ts` — параллельно загружает session
  и filtered ledger.
- `frontend/app/routes/import-review.tsx` — переводит loader result в
  `ImportReviewPage` или 401/403/404/error UI.
- `frontend/app/routes/import-review-loader.ts` — параллельно загружает session
  и document review.
- `frontend/app/api/generated/schema.ts` — compile-time представление FastAPI
  OpenAPI; вручную не редактируется.
- `frontend/app/api/session.ts` — загружает session и классифицирует response.
- `frontend/app/api/session-schema.ts` — runtime-проверка session JSON.
- `frontend/app/features/manual-ledger/api/manual-ledger-api.ts` — list/edit
  queries и Zod response schemas.
- `frontend/app/features/manual-ledger/api/manual-ledger-mutations.ts` —
  create/update/lifecycle/delete HTTP commands и typed result unions.
- `frontend/app/features/manual-ledger/list/manual-ledger-page.tsx` — владелец
  list UI state и локальной reconciliation.
- `frontend/app/features/manual-ledger/list/manual-ledger-filter-query.ts` —
  чистое преобразование URL query ↔ filter draft.
- `frontend/app/features/manual-ledger/operation/manual-operation-draft.ts` —
  form draft ↔ generated API command.
- `frontend/app/features/manual-ledger/operation/manual-operation-form.tsx` —
  общие create/edit fields.
- `frontend/app/features/import-review/api/import-review-api.ts` — query и
  runtime schema полного review snapshot.
- `frontend/app/features/import-review/api/import-review-mutations.ts` —
  feature-local mutation transport и response validation.
- `frontend/app/features/import-review/import-review-page.tsx` — владелец
  authoritative document snapshot, URL filter и visible-row window.
- `frontend/app/features/import-review/review-item.tsx` — собирает row,
  actions, panels, raw source и presentation mapping.
- `frontend/app/features/import-review/classification-panel.tsx` — controlled
  draft, async server evaluation и category creation.
- `frontend/app/ui/workbench-row/workbench-row.tsx` — общая геометрия
  финансовой строки без workflow rules.
- `frontend/app/ui/action-stack/action-stack.tsx` — primary/secondary/overflow/
  danger composition.
- `frontend/app/ui/field/*` — label/hint/error/layout primitives.
- `frontend/app/styles/themes/*.css` — palette и semantic role mapping.
- `src/app/api/v1/manual_ledger/router.py` — workspace-scoped ledger JSON
  query/commands.
- `src/app/api/v1/import_review/router.py` — review query, classification,
  category, transfer, lifecycle, rule commands.
- `src/app/api/v1/import_review/posting_router.py` — confirm/post/undo commands.
- `src/app/react_frontend.py` — SPA assets/fallback и historical redirects.

### Смешанная или неочевидная ответственность

| Файл                         | Почему ответственность размыта                                                                                           |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `review-item.tsx`            | row composition, copy mapping, source diff, money formatting, lifecycle policy presentation и outcome view в одном файле |
| `classification-panel.tsx`   | state machine, async orchestration, two field groups и nested category form                                              |
| `import-review.module.css`   | page, queue, reconciliation, row, forms, panels и responsive rules одного feature                                        |
| `manual-ledger-mutations.ts` | четыре commands плюс повторяющийся transport/error parser                                                                |
| `session-schema.ts`          | handwritten schema повторяет generated `SessionDto`; полезно, но ownership контракта двойное                             |

### Оценка структуры и зависимостей

- Циклических и cross-feature imports не найдено.
- Feature internals импортируются только route adapter-ами; одна feature не
  знает внутренности другой.
- Относительные imports местами имеют три `../`, но ведут прямо к
  defining module и пока понятнее alias/barrel layer.
- Barrel files отсутствуют; source ownership находится быстро.
- `ui/` не импортирует features, `shared/` не импортирует UI/routes/features.
- API access не встречается в случайных visual components: `fetch` ограничен
  session и feature API modules.
- Имена файлов и компонентов domain-specific и последовательны.
- Структура Manual Ledger показывает хороший progressive split: feature не
  раздроблена на десятки файлов, но list и operation имеют разные владельцы.
- Import Review правильно остался более плоским на первой миграции, однако
  теперь накопил достаточно evidence для focused split P3.

---

## C. Как работают две страницы

### C1. Manual Ledger

Полный поток:

```text
/app/ledger/manual?filters
→ routes/manual-ledger.tsx clientLoader
→ loadManualLedgerRoute(request)
→ Promise.all(loadSession, loadManualLedger)
→ GET /api/v1/session + GET /api/v1/manual-ledger?...
→ FastAPI router → ManualOperationService/reference reader
→ Pydantic camelCase DTO
→ Zod manualLedgerSchema
→ loaderData
→ ManualLedgerPage local UI/reconciliation state
→ WorkbenchRow + ManualOperationRow
→ create/edit/lifecycle/delete command
→ CSRF + version/idempotency key
→ authoritative operation response
→ local overlay + route revalidate/navigation
```

Entry point: `routes.ts` → `routes/manual-ledger.tsx`.

Page component: `ManualLedgerPage`.

Server state:

- loader владеет fetched list;
- URL владеет search/filter/page/per-page/target operation;
- `localChanges` временно удерживает более свежий mutation response до
  завершения revalidation;
- form drafts находятся внутри create/edit components;
- pending state находится у конкретной row/form.

Формы:

- create и edit используют одни controlled fields через
  `ManualOperationFields`;
- HTML `required` обеспечивает базовую browser validation;
- FastAPI/Pydantic/application возвращают authoritative `422 fieldErrors`;
- `FormErrorSummary` связывает summary с полями;
- после `422` draft сохраняется, первое invalid field получает focus;
- pending submit блокирует повторный запрос;
- create сохраняет один `Idempotency-Key` на retry;
- update/lifecycle/delete используют version для optimistic concurrency.

После mutation:

- create закрывает dialog и навигирует на target operation;
- edit/lifecycle кладут server operation в local reconciliation;
- route вызывает `revalidator.revalidate()`;
- delete скрывает строку локально до обновления list;
- при `409` draft/row остаётся на месте и предлагается refresh.

Loading/error/success:

- initial client load — `HydrateFallback`;
- route errors — login/retry state;
- edit имеет local loading/retry;
- form errors inline и в summary;
- success не использует toast: он выражен закрытием формы, target row и
  authoritative status. Это приемлемо для текущего workflow.

Styles: один feature CSS Module плюс shared component modules; global palette и
foundation приходят через `app.css`.

Зависимости страницы: React, React Router, Zod, generated OpenAPI types,
Phosphor icons и собственные UI primitives. Query/form/state libraries нет.

Что важно понять Python-разработчику:

`ManualOperationDraft` близок к отдельной input DTO, но не является Pydantic
model и не валидирует runtime data. Функция `manualOperationCreateRequest`
превращает UI draft в один из generated discriminated request types. Настоящая
финансовая валидация всё равно выполняется FastAPI/application.

### C2. Import Review

Полный поток:

```text
/app/imports/documents/:documentId/review
→ routes/import-review.tsx clientLoader
→ loadImportReviewRoute(documentId)
→ Promise.all(loadSession, loadImportReview)
→ GET /api/v1/session + GET /api/v1/import-review/:id
→ ImportReviewReader + response mapper
→ Pydantic DTO
→ Zod importReviewSchema
→ ImportReviewPage
→ currentReview authoritative snapshot in feature-local state
→ URL filter/visible rows + ReviewItem components
→ draft-evaluation/category/transfer/lifecycle/confirm/undo/apply-rules
→ CSRF + expectedStatus/idempotency key where required
→ committed document snapshot(s)
→ reconcileReview(nextReview)
→ queue, rows, capabilities and validation rerender together
```

Entry point: `routes.ts` → `routes/import-review.tsx`.

Page component: `ImportReviewPage`; keyed wrapper сбрасывает feature state при
переходе к другому document.

Server state:

- initial snapshot приходит из loader;
- после mutation `currentReview` заменяется только server response;
- `categories` — локально расширяемая reference collection для только что
  созданной category;
- URL хранит `filter` и число раскрытых rows;
- classification/transfer/rule drafts живут у конкретной строки;
- открытые panels и menus — ephemeral row state.

Формы и actions:

- ordinary classification — controlled selects + async server evaluation;
- category creation — отдельная native form;
- transfer — controlled select + discriminated command;
- confirm optionally creates a rule and reuses idempotency key until selection
  changes;
- lifecycle and undo require explicit confirmation for destructive actions;
- request-id refs защищают classification от out-of-order responses;
- errors остаются local; network error не уничтожает draft.

После mutation:

- backend возвращает полный snapshot каждого затронутого document;
- React не пытается вручную пересчитать queue, confirmability или validation;
- cross-document transfer response может содержать несколько reviews;
- текущая страница выбирает snapshot своего document.

Loading/error/success:

- initial route различает 401, 403, 404 и generic error;
- pending состояния локальны action/form;
- `role=status`, `role=alert`, focus recovery и retry используются
  последовательно;
- success выражен изменившимся outcome/status/queue, а не отдельным toast.

Styles: shared Workbench Row/Action Stack/Button и один крупный
`import-review.module.css`.

Зависимости те же; server-state cache library намеренно отсутствует. Для двух
реальных workflows это рационально: mutations уже возвращают smallest truthful
consistency boundary — committed document snapshots.

Что важно понять Python-разработчику:

`currentReview` похож не на ORM entity, а на immutable read-model snapshot.
`setCurrentReview(nextReview)` не мутирует старый объект: React получает новое
значение и заново вычисляет нужные компоненты. Это проще и надёжнее, чем вручную
патчить progress, sibling rows и reconciliation totals.

---

## D. Матрица ответственности

| Модуль/файл                 | Текущая ответственность                 | Проблема                                   | Рекомендуемая ответственность                                  |
| --------------------------- | --------------------------------------- | ------------------------------------------ | -------------------------------------------------------------- |
| route modules               | loader result → page/state UI           | почти нет                                  | оставить                                                       |
| route loaders               | parallel feature/session load           | не передают `request.signal`               | также владеть cancellation                                     |
| `api/session.ts`            | session transport + mapping             | повторяет transport policy                 | session mapping поверх shared request primitive                |
| feature API query files     | URL, fetch, status, JSON, Zod           | transport повторяется                      | feature endpoint + schema + status mapping                     |
| feature mutation files      | command functions + errors              | manual file повторяет четыре fetch blocks  | тонкие commands поверх shared JSON transport                   |
| `ManualLedgerPage`          | list UI/local reconciliation            | много props callbacks, но история единая   | оставить до третьего похожего list workflow                    |
| `manual-operation-form.tsx` | shared create/edit fields               | удачная feature abstraction                | оставить                                                       |
| `ImportReviewPage`          | current snapshot, URL view state, queue | coherent                                   | оставить                                                       |
| `review-item.tsx`           | row + panels + mapping/helpers          | несколько причин изменения                 | row composition отдельно; source/outcome presentation отдельно |
| `classification-panel.tsx`  | draft orchestration + nested form       | на грани                                   | оставить controller; вынести только category form/field group  |
| `ui/field`                  | base form semantics                     | не используется Import Review              | расширить минимально и применить там                           |
| `ActionStack`               | actions + portaled disclosure           | keyboard focus gap                         | добавить disclosure focus contract                             |
| `SearchableSelect`          | accessible searchable combobox          | нет `aria-invalid`, undefined radius token | поддержать invalid state; исправить token                      |
| `import-review.module.css`  | весь feature CSS                        | 1530 строк                                 | 3–4 cohesive modules по компонентным границам                  |
| theme files                 | palette → semantics                     | test theme попадает в production CSS       | решить, нужен ли test theme runtime                            |

---

## E. Найденные проблемы

### P1

ID: P1  
Категория: API / maintainability  
Приоритет: high  
Файлы: `api/session.ts`, оба feature API query/mutation files  
Что происходит: `fetch`, credentials, JSON parsing, API envelope parsing,
network copy и status handling реализованы несколько раз. Manual Ledger и
Import Review по-разному различают `403`/`404`; вызов `response.json()` для
не-JSON `5xx` попадает в `catch` и ошибочно сообщает «Backend недоступен».  
Почему это проблема: следующая страница почти неизбежно скопирует ещё один
вариант transport policy.  
Практическое последствие: непоследовательные сообщения, потеря различия между
network failure и server error.  
Рекомендуемое решение: один маленький `requestJson`/`readApiError` в
`app/api/transport.ts`; feature остаётся владельцем endpoint и result union. Не
создавать универсальный SDK.  
Объём изменения: small/medium.  
Риск изменения: low при API tests.  
Исправлять сейчас: да.

### P2

ID: P2  
Категория: API contracts / TypeScript  
Приоритет: high  
Файлы: `package.json`, generated schema workflow  
Что происходит: generated types committed, но `npm run check` не экспортирует
OpenAPI и не проверяет diff. Zod schemas типизированы относительно текущего
generated file, а не обязательно текущего backend.  
Почему это проблема: backend schema и generated TS могут расходиться, а lint/
type/test останутся зелёными.  
Практическое последствие: runtime rejection корректного нового response или
отправка устаревшего request.  
Рекомендуемое решение: отдельный deterministic `api:check`, который генерирует
во временный файл и падает при diff. Не генерировать молча во время build.  
Объём изменения: small.  
Риск изменения: low.  
Исправлять сейчас: да.

### P3

ID: P3  
Категория: component cohesion  
Приоритет: high  
Файлы: `review-item.tsx`, `import-review.module.css`  
Что происходит: 889-line component module содержит composition, source
comparison, outcome mapping, status copy, money formatting и lifecycle action
grouping; 1530-line CSS обслуживает почти весь feature.  
Почему это проблема: поиск и review следующего изменения требуют читать
несвязанные истории; merge conflicts будут расти.  
Практическое последствие: import-review становится труднее сопровождать, чем
остальной frontend.  
Рекомендуемое решение: разделить по 3 устойчивым причинам изменения:
`review-item.tsx`, `review-item-presentation.ts`, `source-comparison.tsx`; CSS —
page/row/editor modules. Не делать «одна функция — один файл».  
Объём изменения: medium.  
Риск изменения: medium; нужен полный component/browser gate.  
Исправлять сейчас: да, до активной параллельной миграции.

### P4

ID: P4  
Категория: accessibility  
Приоритет: high  
Файлы: `ui/action-stack/action-stack.tsx`  
Что происходит: overflow content portal-ится в конец `body`, но после открытия
focus остаётся на trigger. Следующий Tab следует document order, а не
визуальному popup.  
Почему это проблема: keyboard user может не попасть в открытые actions
предсказуемо.  
Практическое последствие: действия, особенно danger actions, сложнее или
невозможно обнаружить без мыши.  
Рекомендуемое решение: при keyboard/open переводить focus на первую action;
реализовать Tab/Escape/return-focus contract. Не обязательно превращать
disclosure в ARIA `menu`.  
Объём изменения: small.  
Риск изменения: low/medium.  
Исправлять сейчас: да.

### P5

ID: P5  
Категория: forms / accessibility  
Приоритет: medium  
Файлы: `classification-panel.tsx`, `searchable-select.tsx`  
Что происходит: import-review errors связаны через `aria-describedby`, но
category, property и category-name controls не получают `aria-invalid`.
`SearchableSelect` не принимает этот prop.  
Почему это проблема: screen reader не получает стандартный invalid-state
signal.  
Практическое последствие: error text существует, но форма менее понятна
assistive technology.  
Рекомендуемое решение: добавить typed `aria-invalid` в SearchableSelect и
использовать shared `Field`/`FormError` там, где это не ломает layout.  
Объём изменения: small.  
Риск изменения: low.  
Исправлять сейчас: да.

### P6

ID: P6  
Категория: async correctness  
Приоритет: medium  
Файлы: route loaders, feature API functions, edit/classification/actions  
Что происходит: API functions не принимают `AbortSignal`. Classification
игнорирует устаревшие ответы по request id, но продолжает запрос; edit/actions
не имеют общего unmount/cancel contract.  
Почему это проблема: navigation не отменяет работу; новые workflows с search
или rapid navigation усилят race risk.  
Практическое последствие: лишняя сеть и потенциально поздний local feedback.  
Рекомендуемое решение: передавать `request.signal` из clientLoader и optional
signal в query calls; для draft evaluation использовать AbortController вместе
с request-id guard. Mutations не отменять автоматически после отправки
финансовой команды — ответ может быть нужен для reconciliation.  
Объём изменения: medium.  
Риск изменения: medium.  
Исправлять сейчас: loaders/queries сейчас; financial mutations позже и
осознанно.

### P7

ID: P7  
Категория: TypeScript modelling  
Приоритет: medium  
Файлы: `posting-actions.tsx`, `classification-panel.tsx`,
`lifecycle-actions.tsx`  
Что происходит: error helpers принимают `{status: string}`, а category kind
получается через unchecked `as`.  
Почему это проблема: discriminated union теряет exhaustiveness именно перед
показом ошибок; assertion создаёт ложную уверенность.  
Практическое последствие: новый result status может молча получить generic
copy.  
Рекомендуемое решение: принимать точный result union и использовать exhaustive
switch; category kind parse/narrow через маленькую функцию.  
Объём изменения: small.  
Риск изменения: low.  
Исправлять сейчас: да в normalization slice.

### P8

ID: P8  
Категория: CSS correctness  
Приоритет: medium  
Файлы: `searchable-select.module.css`, `tokens.css`,
`scripts/check-styles.mjs`  
Что происходит: используется отсутствующий `--radius-xs`; текущий style check
проверяет theme contract, но не все `var()` references.  
Почему это проблема: declaration становится invalid, а зелёный check создаёт
ложное чувство безопасности.  
Практическое последствие: option radius не применяется.  
Рекомендуемое решение: заменить на существующий `--radius-sm` либо определить
действительно нужный primitive; добавить missing-token scan.  
Объём изменения: small.  
Риск изменения: low.  
Исправлять сейчас: да.

### P9

ID: P9  
Категория: forms / CSS reuse  
Приоритет: medium  
Файлы: `classification-panel.tsx`, `transfer-panel.tsx`,
`posting-actions.tsx`, `import-review.module.css`, `ui/field/*`  
Что происходит: Import Review вручную повторяет label/input/error/control
chrome, уже имеющийся в shared Field.  
Почему это проблема: визуальные и accessibility fixes придётся делать дважды.  
Практическое последствие: Manual Ledger и Import Review формы расходятся.  
Рекомендуемое решение: переиспользовать `Field`, `FormError` и `FormActions`;
оставить feature-specific grids, SearchableSelect composition и workflow copy
локальными.  
Объём изменения: medium.  
Риск изменения: low/medium.  
Исправлять сейчас: да после P5.

### P10

ID: P10  
Категория: runtime validation  
Приоритет: medium  
Файлы: `session-schema.ts`, оба feature API files  
Что происходит: generated DTO и большие handwritten Zod schemas описывают один
контракт дважды. `z.ZodType<GeneratedDto>` даёт compile-time связь, но поля и
enum всё равно повторяются вручную.  
Почему это проблема: цена каждого API изменения удваивается.  
Практическое последствие: schema change требует backend, generation и ручного
Zod update.  
Рекомендуемое решение: пока сохранить runtime validation, потому что она
реально ловит malformed response. После P2 сравнить:
генерируемые runtime schemas либо focused boundary validation только
критичных/используемых частей. Не добавлять вторую schema library.  
Объём изменения: medium/high.  
Риск изменения: medium.  
Исправлять сейчас: позже.

### P11

ID: P11  
Категория: state complexity  
Приоритет: low  
Файлы: `manual-ledger-page.tsx`, `manual-ledger-reconciliation.ts`  
Что происходит: list хранит локальный updated/deleted overlay и одновременно
запускает route revalidation.  
Почему это проблема: это временное дублирование server state.  
Практическое последствие: дополнительный reconciliation code.  
Рекомендуемое решение: оставить. Здесь abstraction имеет доказанную цель:
server response видим сразу, а loader не успевает вернуть старую версию. Убирать
только при переходе на единый router action/cache mechanism.  
Объём изменения: none.  
Риск изменения: выше выгоды.  
Исправлять сейчас: нет.

### P12

ID: P12  
Категория: theme delivery  
Приоритет: low  
Файлы: `root.tsx`, `themes/index.css`, `themes/test.css`  
Что происходит: root жёстко выбирает Mocha; Latte готова, но UI/persistence для
switch нет. Test theme импортируется в production CSS.  
Почему это проблема: theme-ready architecture есть, но runtime product feature
не завершена.  
Практическое последствие: пользователь не может сменить тему; небольшой лишний
CSS test payload.  
Рекомендуемое решение: отдельно принять product decision о theme preference;
test theme исключить из production index либо явно оставить gallery-only.  
Объём изменения: small/medium.  
Риск изменения: low.  
Исправлять сейчас: позже.

---

## F. Дублирование и переиспользование

### Уже удачно переиспользуется

- Button/IconButton и icon renderer.
- Field/Fieldset/FormErrorSummary/FormActions.
- MoneyValue, StatusLabel, Tag, Badge.
- WorkbenchRow и ActionStack между обеими страницами.
- ExpansionPanel, ConfirmationDialog, WorkbenchPanel.
- RequestState.
- Date/money formatting для Manual Ledger.
- Session/AppShell.

### Реальное дублирование

| Вид                            | Где                                   | Решение                                                           |
| ------------------------------ | ------------------------------------- | ----------------------------------------------------------------- |
| fetch/error envelope           | session + обе feature API             | shared thin transport                                             |
| Zod operation/status fragments | query/mutation schemas                | feature-local schema composition                                  |
| field chrome/errors            | Import Review vs `ui/field`           | переиспользовать primitives                                       |
| decimal formatting             | `format-money.ts` и `review-item.tsx` | общий decimal-string formatter с явным semantic sign              |
| operation labels/tones         | manual model и review item            | общий mapping только если третий consumer подтвердит стабильность |
| retry/refresh copy             | action components                     | не делать generic hook; можно общий typed error mapper            |

### Похожее, что не нужно объединять

- Manual operation form и import classification panel: первая редактирует
  ledger command, вторая проверяет raw import draft.
- Manual local row reconciliation и full import snapshot reconciliation:
  consistency boundaries различны.
- WorkbenchPanel dialog и inline ExpansionPanel: разные focus/navigation
  semantics.
- Manual filters и Import Review filter chips: разные URL state и interaction.
- Lifecycle actions Manual Ledger и Import Review: похожий UI, но разные backend
  transitions и concurrency tokens.

### Overengineering, которого нет

- нет Redux/global entity cache;
- нет Context providers для server state;
- нет generic FormBuilder;
- нет barrel chains;
- нет custom hooks, скрывающих один fetch;
- нет избыточных generics;
- нет `React.memo`, `useMemo` или `useCallback` «на всякий случай»;
- существующие `useMemo`/`useCallback` имеют конкретную identity/computation
  причину.

---

## G. CSS и темизация

### Текущая архитектура

```text
tokens.css
  geometry / spacing / typography / motion

themes/catppuccin-*.css
  raw Catppuccin palette
  → semantic color roles

foundation.css
  reset / body / focus / reduced motion / visually hidden

*.module.css
  shell, shared components, features
```

Это последовательный **CSS Modules + semantic custom properties** подход.
Legacy SSR продолжает использовать `src/app/static/css/app.css`, но React
bundle его не импортирует. Поэтому selector conflicts между React feature CSS и
legacy CSS практически исключены.

Сильные стороны:

- raw hex/rgb запрещены вне theme directory;
- компоненты используют semantic `--color-*`, а не Catppuccin primitives;
- contrast проверяется script-ом;
- spacing/radius/type/control-size tokens общие;
- focus-visible и reduced-motion глобальны;
- financial roles не зависят только от цвета: есть labels/status copy/icons;
- responsive rules проверялись на 1440/920/390 px;
- `!important` почти отсутствует и в основном оправдан reset/reduced-motion.

Проблемы:

- `import-review.module.css` слишком велик;
- `--radius-xs` отсутствует;
- z-index scale неполный: есть `--z-header`, а popup layers выражены через
  arithmetic и один raw `20`;
- breakpoints повторяются как 35/45/57.5/70/75rem. Это пока объясняется
  layout boundaries, но новые страницы должны выбирать из существующих;
- Import Review повторяет field CSS;
- test theme включена в production CSS;
- component tokens почти отсутствуют. Сейчас это нормально: добавлять
  `--button-*` слой для каждого свойства не нужно.

### Готовность к Catppuccin

**Уже готово и фактически реализовано.** Mocha — default, Latte — полноценная
light theme. Для новой Catppuccin flavor достаточно нового theme file с тем же
semantic contract; компоненты менять не нужно.

Не хватает только product/runtime части:

- выбор темы;
- persistence;
- системная preference policy;
- исключение test-only theme из production при необходимости.

Новая палитра должна определять только semantic color/shadow contract. Spacing,
radius и component geometry не нужно копировать в каждую theme.

### Минимальный UI-контракт

Следующие страницы должны использовать:

- `AppShell` и один `h1`;
- `PageHeader` для обычных workbench pages;
- `WorkbenchRow` для повторяющихся финансовых сущностей;
- Button/IconButton с 44px minimum target;
- Field/Fieldset/FormError/FormErrorSummary;
- RequestState для loading/empty/error;
- ConfirmationDialog для destructive commit;
- ExpansionPanel для inline row work, WorkbenchPanel для modal create;
- MoneyValue + decimal strings;
- StatusLabel/Tag/Badge по отдельной семантике;
- semantic tokens, CSS Modules и существующие responsive boundaries;
- local pending/error state и authoritative success response.

### Единообразие двух страниц

Совпадает:

- AppShell, responsive navigation и content width;
- financial row geometry;
- buttons, money, tags, statuses и action grouping;
- inline panels, destructive confirmation и focus return;
- semantic colors, spacing scale и 44px controls;
- authoritative success и local error feedback;
- desktop/tablet/mobile adaptation.

Осознанно различается:

- Manual Ledger использует PageHeader и list toolbar, Import Review — document
  summary + queue progress;
- Manual create открывается modal panel, import classification раскрывается
  внутри строки;
- Manual filters — form с Apply, Import Review filters — immediate pressed
  buttons;
- Manual list pagination server-side, Import Review раскрывает уже загруженную
  queue блоками по 50.

Необоснованно различается:

- field/error chrome и `aria-invalid`;
- часть money/status presentation helpers;
- detail уровня API error messages.

---

## H. Минимальная целевая архитектура

Текущую форму нужно сохранить:

```text
app/
├── api/
│   ├── generated/
│   ├── transport.ts          # только HTTP/JSON/error envelope
│   └── session.*
├── routes/                   # route adapters/loaders
├── features/
│   └── feature/
│       ├── api/              # endpoints, schemas, typed results
│       ├── page-or-list/     # только когда feature реально сложный
│       ├── entity-or-flow/   # только устойчивые sub-responsibilities
│       └── *.module.css
├── ui/                       # стабильные product-wide UI responsibilities
├── shared/                   # pure format/parse functions, не feature logic
├── shell/
└── styles/
```

Разрешённые зависимости:

```text
routes → features + api/session
features → api/generated + ui + shared + shell
ui → shared (редко) + React
shared → ничего feature-specific
```

Запрещённые зависимости:

```text
ui → features
feature A → internals feature B
shared → route/session/feature
component → FastAPI details outside feature API
React → financial policy replicated from backend
```

Public `index.ts` API не нужен, пока feature не имеет внешних consumers кроме
route. Явные imports из defining module сейчас помогают найти ownership.

Не добавлять:

- глобальный state manager;
- React Query только ради стандартизации двух loaders;
- form library;
- FSD layers;
- generic CRUD/form config;
- component mega-library;
- alias/import magic вместо ясных relative imports.

---

## I. Checklist для следующих React-страниц

### До реализации

- Зафиксировать canonical user flow и legacy behavior inventory.
- Назвать financial/security/workspace invariants.
- Определить server DTO без HTML/layout/action placement.
- Выбрать state owner: server, URL, form draft, ephemeral component или app
  context.
- Определить smallest truthful mutation response.
- Составить exact legacy consumer/delete list.

### API

- Workspace scope проверяется сервером.
- Capabilities возвращаются сервером и повторно проверяются command endpoint.
- Money — decimal string; date/time — документированный формат.
- Requests/responses есть в OpenAPI.
- Generated types обновлены и drift check зелёный.
- Runtime boundary проверяет unknown JSON.
- 401/403/404/409/422/5xx имеют явный UI outcome.
- Unsafe request использует CSRF; финансовый create/post — idempotency audit.
- Loader query принимает AbortSignal.

### React/state

- Route component остаётся тонким.
- Server state не копируется без consistency-причины.
- Filters/pagination/deep-link target находятся в URL.
- Derived values вычисляются, а не синхронизируются effect-ом.
- Effect используется только для external synchronization.
- Pending блокирует конфликтующий повторный command.
- Confirmed financial state появляется только после server response.
- 409 предлагает refresh; 422 сохраняет draft.
- Не добавляется memoization без измерения.

### Forms/accessibility

- Native `form`, `button`, `label`, `fieldset`, `input/select`.
- Label связан с control.
- Required обозначен визуально и семантически.
- Error связан через `aria-describedby`; invalid control имеет `aria-invalid`.
- Error summary/focus first invalid для длинной формы.
- Dialog имеет accessible name, Escape, trap и return focus.
- Portaled popup имеет понятный keyboard focus path.
- 44px target, visible focus и отсутствие color-only meaning.

### UI/CSS

- Сначала используются существующие primitives.
- Feature-specific semantics остаются в feature.
- Новый shared component появляется только при стабильной ответственности.
- CSS Module не смешивает несколько больших component stories.
- Только semantic color tokens.
- Существующий spacing/radius/breakpoint rhythm.
- Desktop/920/mobile без horizontal overflow.
- Mocha и Latte проверены.

### Tests/cutover

- query success/error/malformed response;
- page loading/error/empty/readonly;
- critical create/edit/lifecycle mutation;
- 422 draft/field focus;
- 409 refresh;
- session expiry/permissions;
- idempotency/concurrency;
- component keyboard behavior;
- realistic browser flow;
- legacy удаляется только после consumer search и replacement gate.

---

## J. План изменений

### Этап 0 — ничего не менять

Цель: зафиксировать решения.

- Принять этот аудит и подтвердить normalization scope.
- Оставить feature-local state, route loaders и отсутствие cache/form/state
  libraries.
- Оставить manual reconciliation.
- Записать, является ли theme switch product feature Stage 07.

Риск: отсутствует.  
Тесты: не нужны.  
Критерий: решения отражены в следующем focused child stage.

### Этап 1 — безопасная нормализация

Конкретные изменения:

- `app/api/transport.ts`: safe JSON/error envelope parsing и единые network/
  HTTP outcomes;
- добавить `api:check`;
- исправить `--radius-xs` и missing-token validation;
- добавить `aria-invalid` в import fields/SearchableSelect;
- исправить keyboard focus ActionStack;
- заменить broad `status: string` и unchecked category assertion;
- переиспользовать shared money decimal formatter.

Ожидаемый результат: следующие features не копируют transport/forms defects.  
Риск: low.  
Тесты: API adapter unit tests, ActionStack/SearchableSelect keyboard tests,
styles check, полный `npm run check`.  
Критерий: единый transport primitive, OpenAPI drift обнаруживается, P4/P5/P8
закрыты.

### Этап 2 — архитектурные улучшения

Конкретные изменения:

- разделить `review-item.tsx` по трём cohesive stories;
- разделить import CSS на page/row/editor modules;
- перевести import fields на shared form primitives;
- добавить AbortSignal в loaders/queries;
- решить подход к generated/runtime schemas отдельным ADR.

Ожидаемый результат: Import Review становится эталоном, который проще читать,
чем копировать.  
Риск: medium.  
Тесты: все 151 frontend tests, focused browser import-review flow,
desktop/920/mobile, API contract tests.  
Критерий: нет файлов, рассказывающих несколько несвязанных историй; behavior и
bundle geometry не изменены.

Completed: 2026-07-23.

Implemented:

- `review-item.tsx` разделён на composition, presentation и source comparison;
- feature CSS разделён на page, row и editor modules;
- classification, category, transfer и posting fields используют shared
  `Field`;
- loader/query cancellation закрыт в этапе 1;
- подход к generated DTO и runtime Zod зафиксирован в ADR-0005.

Checks run: frontend format, lint, styles, OpenAPI drift, typecheck, 157 tests,
production build и 23 Import Review API contract tests.

Browser follow-up: `ui_audit.py` создал desktop/920/mobile screenshots; они
проверены вручную, root horizontal overflow отсутствует. Автоматизированный
`react-import-review` scenario пока завершается timeout на history
`wait_for_function` после успешной загрузки: console/page/request/UX assertion
errors отсутствуют. Это отдельный audit-tooling follow-up, не скрытый зелёный
gate.

### Этап 3 — SSR legacy

Для этих двух страниц удалять больше почти нечего.

Оставить сейчас:

- historical GET redirects в `src/app/react_frontend.py`;
- legacy `app.css`, Jinja UI и `entity-target.js`, потому что их используют
  остальные SSR pages;
- import application/domain/read models и chat presentation;
- raw transaction legacy selectors, используемые document detail page;
- `templates/ui/_more_actions.html` и `review-actions__*`, используемые
  transaction rules.

Удалить только после последней authenticated migration:

- redirects и временный `/app` prefix после canonical URL decision;
- legacy global CSS и JS после consumer search;
- remaining authenticated templates/routers/presenters;
- redirect-only Playwright branches.

Риск: high при преждевременном удалении.  
Тесты: canonical deep links, redirects, public/auth pages, full backend suite,
frontend check, Playwright route matrix.  
Критерий: React — единственный authenticated frontend, а legacy asset не имеет
ни одного runtime consumer.

Completed: 2026-07-23.

Consumer search:

- legacy Manual Ledger и Import Review templates, HTML routes и browser
  presenters отсутствуют;
- `/ledger/manual` и `/imports/documents/{document_id}/review` существуют только
  как query-preserving redirects в `react_frontend.py`;
- `app.css`, HTMX, Alpine и `entity-target.js` подключены общим SSR
  `base.html`, который используют оставшиеся authenticated workflows;
- `entity-target.js` обслуживает accounts, categories, properties и transaction
  rules;
- raw-transaction selectors используются document detail;
- `_more_actions.html` и `review-actions__*` используются categories и
  transaction rules;
- application/domain/read models и chat presentation имеют независимых
  runtime consumers.

Cleanup performed: production-файлы не удалялись. Это осознанный результат
delete gate: каждый оставшийся legacy target имеет именованного потребителя.
Redirects, общий SSR asset stack и redirect-aware UI audit branches остаются до
последней authenticated migration.

Checks run:

- authenticated Chromium route matrix для Manual Ledger redirect — desktop,
  920 и mobile passed;
- authenticated Chromium route matrix для historical Import Review redirect —
  desktop, 920 и mobile passed;
- redirect и base-template tests — 9 passed;
- full backend suite — 550 passed;
- Ruff lint и `ty` passed;
- полный `npm run check` — 157 frontend tests и production build passed.

Known baseline issue: `ruff format --check .` сообщает о четырёх ранее
неформатированных файлах вне этого cleanup slice; они не изменялись.

---

## Примеры минимальных улучшений

### 1. Общий transport без generic SDK

До:

```ts
const response = await fetch(url, options);
const body: unknown = await response.json();
const error = apiErrorSchema.safeParse(body);
```

После:

```ts
const response = await requestJson(url, {
  ...options,
  signal,
});

if (!response.ok) {
  return mapImportReviewError(response);
}
return parseImportReview(response.body);
```

`requestJson` знает только HTTP/JSON. Feature по-прежнему знает смысл status и
DTO. Это аналог небольшого Python HTTP adapter, а не нового service framework.

### 2. Сохранение точного union в error mapping

До:

```ts
function postingError(result: { status: string; message?: string }): string {
  if (result.status === "unauthenticated") return "...";
  return result.message ?? "...";
}
```

После:

```ts
function postingError(
  result: Exclude<ImportReviewMutationResult<unknown>, { status: "success" }>,
): string {
  switch (result.status) {
    case "unauthenticated":
      return "Сессия завершилась.";
    case "forbidden":
      return "Недостаточно прав.";
    case "validation_error":
    case "conflict":
    case "error":
      return result.message;
  }
}
```

Теперь TypeScript заставит обработать новый status. Это близко к exhaustive
match по `Literal` union в Python.

### 3. Invalid-state для searchable field

До:

```tsx
<SearchableSelect
  aria-describedby={error ? errorId : undefined}
  ...
/>
```

После:

```tsx
<SearchableSelect
  aria-describedby={error ? errorId : undefined}
  aria-invalid={Boolean(error)}
  ...
/>
```

Видимый текст уже был; изменение добавляет стандартную semantics для assistive
technology.

### 4. Cohesive split Review Item

До:

```tsx
// review-item.tsx: composition + source comparison + mapping + formatting
export function ReviewItem(...) { ... }
function SourceComparison(...) { ... }
function reviewOutcomePresentation(...) { ... }
function statusLabel(...) { ... }
```

После:

```tsx
// review-item.tsx
export function ReviewItem(...) {
  const presentation = presentReviewItem(item, references);
  return <WorkbenchRow ... />;
}

// review-item-presentation.ts
export function presentReviewItem(...) { ... }

// source-comparison.tsx
export function SourceComparison(...) { ... }
```

Это не дробление по функциям: выделяются три разные причины изменения —
composition, pure presentation mapping и parser traceability.

### 5. OpenAPI drift gate

До:

```json
"check": "format && lint && styles && typecheck && test && build"
```

После:

```json
"api:check": "generate-to-temp-and-compare",
"check": "format && lint && styles && api:check && typecheck && test && build"
```

Generated файл остаётся committed и reviewable, но stale contract больше не
может пройти зелёный check.

---

## Accessibility classification

Критичные:

- не обнаружены: native dialogs, labels, buttons, focus-visible и server error
  semantics в целом корректны.

Важные:

- P4: focus path portaled ActionStack;
- P5: incomplete invalid-state semantics в Import Review.

Желательные:

- автоматизированный axe smoke для foundation и двух pages;
- тест Tab order для ActionStack/SearchableSelect;
- явно документировать initial focus WorkbenchPanel;
- при будущих long forms добавить unsaved-dismiss confirmation.

---

## Тестируемость и фактические проверки

Имеется:

- unit tests чистых format/filter/pagination/reconciliation functions;
- component/integration tests React Testing Library;
- route/loader tests;
- API adapter malformed-response tests;
- backend FastAPI contract/auth/workspace/422/409/idempotency tests;
- domain/application financial tests;
- Playwright realistic browser audit и screenshots;
- theme contrast/style policy tests.

Не имеется как постоянный отдельный слой:

- visual-regression snapshot comparison;
- axe accessibility runner;
- production telemetry/performance SLA;
- автоматический OpenAPI drift gate.

Рациональный minimum для следующих страниц:

1. один query adapter test: success/status/malformed;
2. page state test: success/empty/error/readonly;
3. один test на каждый финансово различимый command;
4. `422` draft + field focus и `409` refresh;
5. backend workspace/auth/financial invariants;
6. один realistic Playwright flow на desktop и mobile;
7. shared primitive tests только для сложной keyboard/focus behavior.

`npm run check` на момент аудита:

- Prettier: passed;
- ESLint: passed;
- style policy/contrast: passed;
- TypeScript strict check: passed;
- Vitest: **23 files, 151 tests passed**;
- production build: passed при разрешении локального preview bind.

Первый sandboxed build создал assets, но завершился с `listen EPERM
127.0.0.1` на prerender preview; повторный build вне этого sandbox-ограничения
полностью прошёл. Это ограничение среды проверки, не defect приложения.
