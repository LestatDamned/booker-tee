# Проектирование React Frontend

Статус: активная целевая архитектура нового browser frontend.

Решение принято владельцем проекта 20 июля 2026 года после аудита current SSR,
Frontend Next, связанных presentation-слоев, CSS, JavaScript, UI-тестов и
миграционной документации.

Этот документ задает:

- целевую границу React frontend и FastAPI JSON API;
- переносимые продуктовые, UX/UI и interaction-контракты;
- правила владения состоянием и финансовой семантикой;
- стратегию вертикальной миграции;
- repository cleanup manifest;
- условия удаления current SSR и незавершенного SSR Frontend Next.

До выполнения документационного cleanup этот документ имеет приоритет над
[`FRONTEND_NEXT_DESIGN.md`](FRONTEND_NEXT_DESIGN.md) в вопросах целевого frontend
stack, расположения нового frontend-кода и дальнейшей миграции workflows.
[`DESIGN.md`](DESIGN.md) остается источником продуктового UX и визуального языка,
а [`WORKBENCH_ROW_DESIGN.md`](WORKBENCH_ROW_DESIGN.md),
[`MANUAL_LEDGER_BASELINE.md`](MANUAL_LEDGER_BASELINE.md) и
[`REFACTOR_PROJECT_DESIGN.md`](REFACTOR_PROJECT_DESIGN.md) используются только
как источники найденного поведения и проверенных контрактов.
Короткие принятые технические решения и их последствия находятся в
[`architecture/decisions`](../architecture/decisions/README.md).
Исполняемая последовательность, current stage и exit gates находятся в
[`frontend/plan`](../frontend/plan/README.md).

---

## 1. Решение

Authenticated financial application Booker Tee переносится на отдельный React
frontend. FastAPI остается владельцем backend, финансового ядра, аутентификации,
workspace authorization, application workflows, persistence, imports и отчетных
read models.

Целевая форма:

```text
Browser
  -> React application
  -> versioned JSON API
  -> application use case / query
  -> repository
  -> PostgreSQL
```

React frontend не обращается к SQLAlchemy models, repositories или Python
presentation ViewModel. FastAPI API не возвращает HTML fragments и не знает о
React components, drawers, CSS classes или расположении кнопок.

Current SSR остается работающим production frontend только на время вертикальной
миграции. `src/app/web/` Frontend Next больше не является целевой платформой и
замораживается: в него не переносятся новые workflows и не добавляются новые
shared SSR abstractions.

### 1.1 Почему меняется предыдущее решение

Работа над manual ledger показала, что он подходит как первый ограниченный
vertical pilot: для него уже существуют current SSR, Frontend Next и подробный
baseline. При этом одного manual ledger недостаточно для оценки самых сложных
frontend workflows. Полный аудит показал:

- browser-oriented legacy routers/presentation Python без chat presentation —
  примерно `10 800` строк;
- current Jinja — `4 555` строк;
- current project CSS и JavaScript без vendor assets — примерно `7 800` строк;
- изолированный SSR Frontend Next — `4 704` строки;
- связанные UI/presentation tests — более `9 000` строк;
- один import workflow содержит `5 352` строки Python presentation/routes и
  `1 347` строк Jinja до учета feature CSS;
- `import review` распределяет одно UI-состояние между Python Presenter, Jinja,
  HTMX/OOB response, Alpine и ручным scroll/focus JavaScript.

Проблема не в абсолютном количестве строк и не в SSR как технологии. Проблема в
том, что интерактивные financial workflows уже требуют client-side state model,
а SSR-реализация строит собственную систему согласования DOM fragments,
response scopes, draft state, focus и sibling updates.

### 1.2 Не цели

В рамках перехода не выполняются:

- переписывание domain/application/repository слоев ради React;
- перенос финансовых правил в TypeScript;
- переход на Node backend или дублирование FastAPI server;
- React Server Components или второй full-stack backend;
- microfrontends и plugin runtime;
- React islands внутри каждой legacy Jinja-страницы;
- глобальный state store до появления доказанной общей client-state задачи;
- декоративный redesign, меняющий финансовую семантику;
- одновременный big-bang rewrite всех маршрутов;
- удаление legacy-кода до появления проверенного replacement workflow.

### 1.3 Инженерные максимы

Эти правила обязательны для архитектурных и code-review решений:

1. **Financial truth остается на server.** React показывает и редактирует
   данные, но не становится вторым владельцем финансовых правил.
2. **Сначала сохраняется рабочая геометрия.** Новый frontend переносит плотность,
   ритм, visual hierarchy, расположение основных зон и responsive behavior
   нынешнего UI. Redesign выполняется отдельно и осознанно.
3. **Theme-ready по умолчанию.** Цвет, typography, spacing, radii, shadows,
   motion и устойчивые control sizes выражаются semantic tokens. Новая тема не
   требует переписывания компонентов.
4. **Переиспользуется ответственность, а не похожий кусок кода.** Устойчивые
   Button, Field, MoneyValue, WorkbenchRow и layout primitives общие; workflow
   rules остаются внутри feature.
5. **Понятность важнее frontend cleverness.** Явные data flow, types и names
   предпочтительнее метапрограммирования, скрытой регистрации, сложных generic
   abstractions и короткого, но непрозрачного кода.
6. **Разработка одновременно обучает владельца проекта.** Новый TypeScript или
   React concept сопровождается объяснением цели, Python-аналогией, trade-off и
   местом в общем request/state/render flow.
7. **Best practice применяется ради конкретного риска.** Dependency, pattern или
   abstraction вводится только когда делает correctness, accessibility,
   testability или сопровождение заметно лучше.
8. **Маленькие вертикальные изменения.** Каждый slice остается читаемым,
   проверяемым и пригодным для обсуждения до следующего слоя сложности.

---

## 2. Источники требований и приоритет

Разные части репозитория имеют разные роли.

| Источник | Что берем | Что не копируем |
| --- | --- | --- |
| Product/domain docs | финансовые инварианты, review-first, privacy, workspace boundary | старые frontend implementation assumptions |
| Current SSR | реальные workflows, edge cases, тексты, permissions, empty/error states | Jinja, HTMX/OOB, Alpine, CSS cascade, HTML response contracts |
| Frontend Next | semantic tokens, Workbench Row, ActionStack, lifecycle, accessibility, `409`/`422` discoveries | Python UI ViewModel, HTML fragment renderers, `/_next`, SSR fallback machinery |
| UI tests and audits | realistic data, behavior baselines, responsive/accessibility failures | exact HTML, CSS selectors и HTMX-specific assertions |
| Git history | удаленная implementation history | production-копии `legacy`, `old`, `next` после cutover |

При конфликте:

```text
financial/domain invariant
  > security/workspace rule
  > this React architecture
  > DESIGN.md UX contract
  > observed legacy behavior
  > legacy implementation detail
```

Current frontend является источником наблюдаемого поведения, но не target code.
Frontend Next является источником проверенных design discoveries, но не target
runtime.

---

## 3. Целевой stack

Начальная целевая конфигурация:

```text
TypeScript in strict mode
React
React Router Framework Mode
SPA mode (`ssr: false`)
Vite-based build supplied by React Router
semantic CSS tokens + global foundation + component CSS Modules
FastAPI `/api/v1`
same-origin session cookie and CSRF header
```

React рекомендует framework для новых приложений с routing. React Router
Framework Mode дает type-safe route modules, code splitting и SPA/SSR/SSG
strategies, а SPA mode отключается явным `ssr: false`. Официальные ссылки:

- [Creating a React App](https://react.dev/learn/creating-a-react-app)
- [React Router: Picking a Mode](https://reactrouter.com/start/modes)
- [React Router: Single Page App](https://reactrouter.com/how-to/spa)

Booker Tee начинает с client-side application, потому что:

- приложение приватное и не нуждается в SEO для financial routes;
- FastAPI уже является полноценным backend;
- второй runtime server не должен дублировать auth, workspace и use cases;
- основной источник сложности — интерактивное client state, а не initial HTML.

React Router framework используется как browser framework, а не как второй
backend. Route `clientLoader`/`clientAction` либо feature API hooks обращаются
напрямую к FastAPI same-origin API.

Не использовать Create React App: он deprecated. Не вводить Next.js только ради
названия `Next`; проекту сейчас не нужны второй server runtime, RSC или SEO SSR.

### 3.1 Dependency policy

Первый scaffold должен оставаться маленьким. На старте нужны только зависимости,
которые закрывают обязательную инфраструктуру:

- React и React DOM;
- React Router Framework Mode;
- TypeScript;
- build/lint/test tooling;
- доступный icon renderer;
- API schema/type generation.

Не добавлять автоматически:

- Redux или другой global store;
- отдельную form framework;
- CSS-in-JS runtime;
- component mega-library;
- chart framework до первого реального chart;
- вторую validation schema, вручную повторяющую Pydantic;
- универсальный API SDK поверх нескольких существующих fetch calls.

Server-state cache library допускается не ранее manual-ledger pilot и только
если route loaders и feature-local data layer не обеспечивают понятную
invalidation. Окончательно потребность проверяется на import review со связанными
rows. Выбор фиксируется отдельным коротким ADR на основании реального workflow,
не популярности библиотеки.

### 3.2 Package management

Frontend использует npm и один committed `package-lock.json`. Clean install
выполняется через `npm ci`, scripts — через `npm run`. Не смешивать npm, pnpm и
yarn. Точные dependency versions фиксирует scaffold-generated lockfile.

Python продолжает использовать `uv`; Node packages не устанавливаются через
Python tooling.

### 3.3 TypeScript и React learning contract

Владелец проекта — Python-разработчик без обязательного предварительного знания
TypeScript и React. Поэтому maintainability включает возможность изучить код по
репозиторию, а не только получить работающий build.

Обязательные правила TypeScript:

- `strict` включен с первого commit и не ослабляется локальными исключениями;
- `any` запрещен, кроме изолированного adapter с объяснением и безопасным
  narrowing;
- входные данные считаются `unknown` до validation/generated contract;
- type assertions `as` и non-null `!` не используются для подавления реальной
  неопределенности;
- discriminated unions описывают конечные состояния request, draft и workflow;
- публичные props, API adapters и feature services имеют явные named types;
- data по возможности immutable; изменение state выполняется видимым способом;
- imports идут из модуля-владельца; barrel files не скрывают ownership;
- функции и types получают domain names, а не `data`, `payload`, `handler` или
  `utils`, если можно назвать ответственность точнее.

Обязательные правила React:

- function components и composition используются как default;
- state живет у ближайшего общего владельца и не копирует server state без
  причины;
- derived values вычисляются при render или focused helper, а не синхронизируются
  отдельным `useEffect`;
- effect используется только для синхронизации с внешней системой и имеет
  понятный cleanup;
- custom hook извлекается при появлении самостоятельного stateful behavior, а
  не для сокрытия каждой пары строк;
- component не выполняет одновременно API orchestration, domain interpretation
  и сложный layout;
- async UI имеет явные idle/loading/success/empty/error/stale states;
- native HTML semantics предпочтительнее воссоздания controls через `div`;
- memoization добавляется после измерения или доказанной identity-проблемы, а не
  как ритуал.

Learning artifacts:

```text
frontend/README.md
  -> как запустить и проверить frontend
  -> request -> state -> render на одном реальном workflow

frontend/docs/typescript-for-python.md
  -> только используемые в проекте TS/JS concepts
  -> Python analogies и важные различия

frontend/docs/decisions/
  -> короткие ADR для неочевидных library/architecture choices
```

При передаче каждого нетривиального React slice нужно кратко объяснить:

1. откуда приходят данные;
2. кто владеет каждым видом state;
3. какие TypeScript/React concepts появились;
4. какой ближайший Python-аналог помогает начать понимание;
5. где аналогия перестает работать;
6. какими тестами подтверждается поведение.

Production comments объясняют **почему** существует ограничение или workaround,
но не превращают каждую строку в учебник синтаксиса. Учебные объяснения живут в
handoff, README и focused docs рядом с кодом.

---

## 4. Целевая структура репозитория

```text
frontend/
  package.json
  react-router.config.ts
  tsconfig.json
  README.md
  app/
    root.tsx
    routes.ts
    routes/
    app/
      api/
      auth/
      routing/
      styles/
    ui/
      button/
      field/
      money-value/
      workbench-row/
      action-stack/
      expansion-panel/
      request-state/
    features/
      shell/
      manual-ledger/
      account-ledger/
      import-documents/
      import-mapping/
      import-review/
      reports/
      categories/
      properties/
      transaction-rules/
      workspaces/
  public/
  tests/
  docs/
    typescript-for-python.md
    decisions/

src/app/
  api/
    router.py
    dependencies.py
    errors.py
    v1/
      router.py
      session/
      ledger/
      imports/
      reports/
      reference_data/
      workspaces/
  features/
    # existing domain/application/repository code
```

Правила:

1. `frontend/` — самостоятельное TypeScript application, не вложенное в
   `src/app/templates` или `src/app/web`.
2. `src/app/api/` — presentation adapter FastAPI JSON, sibling текущих browser
   presentation adapters.
3. API routes вызывают существующие application use cases и queries; они не
   вызывают legacy HTTP routes и не render Jinja.
4. React feature не импортирует внутренности другой feature. Общая UI-концепция
   поднимается в `ui/` после повторного устойчивого использования.
5. Domain terms допускаются в shared UI только как semantic props, например
   `MoneyTone`; `WorkbenchRow` не знает, как подтвердить import row.
6. Generated API types хранятся отдельно от handwritten feature models и не
   редактируются вручную.
7. Build output не является handwritten source и не коммитится, если deployment
   pipeline способен собирать его детерминированно.

---

## 5. Runtime и deployment boundary

Во время миграции:

```text
/                       -> current public SSR home
/login, /signup         -> current SSR auth
/app/*                  -> React application
/api/v1/*               -> FastAPI JSON API
/dashboard, /imports... -> current SSR до workflow cutover
/_next/*                -> frozen SSR Frontend Next до удаления
```

Development:

```text
React dev server
  -> serves frontend and HMR
  -> proxies /api and required auth routes to FastAPI

FastAPI
  -> session/auth/workspace/API/domain/database
```

Production остается same-origin и single-container на первом этапе. Docker
multi-stage build собирает frontend в Node stage; Python runtime раздает
immutable assets и SPA fallback для `/app/*`, а `/api/v1/*` обрабатывает FastAPI.
Reverse proxy/CDN можно добавить позже без изменения frontend/API contracts.
Нельзя включать permissive CORS как замену same-origin setup.

После полного authenticated cutover временный `/app` prefix может быть удален,
а product URLs возвращены к `/dashboard`, `/imports`, `/reports` и другим
каноническим маршрутам. Это отдельный routing cutover, а не причина сохранять
два постоянных frontend.

---

## 6. API boundary

### 6.1 Общий поток

```text
React route / feature
  -> generated API client or focused feature client
  -> FastAPI API endpoint
  -> application query / command
  -> repository
  -> response schema
```

API schemas не являются:

- SQLAlchemy models;
- Jinja ViewModel;
- direct serialization application objects через `__dict__`;
- конфигурацией расположения React-компонентов;
- доверенной security boundary со стороны клиента.

### 6.2 Data conventions

- UUID сериализуется строкой и используется как identity, но не показывается
  пользователю без диагностической причины.
- Money amount передается decimal string, не JSON float.
- Currency передается явно.
- Date — `YYYY-MM-DD`; timestamp — ISO 8601 с timezone.
- Fixed states — string enum с документированными значениями.
- Editable entity содержит integer `version` для optimistic concurrency.
- Pagination response содержит items, page/cursor contract и total только когда
  total действительно нужен UI.
- Server возвращает domain meaning отдельно от display wording.

Пример:

```json
{
  "id": "e4d0...",
  "version": 4,
  "operationDate": "2026-07-20",
  "description": "Перевод на вклад",
  "money": {
    "amount": "15000.00",
    "currency": "RUB",
    "operationType": "transfer",
    "entryDirection": "outflow"
  },
  "status": "confirmed",
  "capabilities": {
    "canEdit": true,
    "canCancel": true,
    "canDelete": false
  }
}
```

React formatter создает locale display из decimal string, currency и готовой
семантики. Он не выводит `operationType` из знака суммы.

### 6.3 Capabilities вместо UI actions

Current SSR и Frontend Next готовят server-owned `ActionVM`. Для React API это
слишком сильная связь с presentation layout.

Server возвращает:

- разрешенные capabilities;
- временную невозможность действия и human-safe reason при необходимости;
- текущее lifecycle state;
- version и ссылки на связанные business resources, если это часть API.

React feature определяет:

- label и icon;
- primary/secondary/more/danger placement;
- drawer, dialog или navigation presentation;
- локальное pending state.

Endpoint всегда повторно проверяет workspace, permission и допустимость
transition. Скрытая кнопка не является защитой.

### 6.4 Error contract

API использует единый envelope:

```json
{
  "error": {
    "code": "stale_version",
    "message": "Операция уже изменилась. Обновите данные и повторите действие.",
    "fieldErrors": {
      "amount": ["Введите сумму больше нуля."]
    }
  }
}
```

Минимальные статусы:

| HTTP | Значение |
| --- | --- |
| `400` | malformed request вне нормального validation contract |
| `401` | нет действующей session |
| `403` | недостаточно permission или invalid CSRF |
| `404` | workspace-scoped resource не найден |
| `409` | stale version или явный state conflict |
| `422` | ожидаемая validation error с сохранением draft на клиенте |
| `5xx` | неожиданная server error без sensitive details |

API не возвращает `303` login redirect, HTML error page или Jinja fragment.
Browser shell обрабатывает `401` и переводит пользователя на login route с
безопасным return URL.

### 6.5 Auth и CSRF prerequisite

Существующая session cookie сохраняется:

- `HttpOnly`;
- `Secure` в production;
- `SameSite=Lax`;
- `Path=/`.

Текущий `get_current_workspace_context` предназначен для HTML:

- отсутствие session превращает в `303`;
- CSRF извлекается только из `request.form()`.

До первой unsafe React mutation нужен отдельный API dependency:

```text
get_api_workspace_context
  -> 401 JSON без session
  -> 403 JSON без permission
  -> workspace-scoped context

verify_api_csrf
  -> X-CSRF-Token header
  -> constant-time validation against current session
```

Bootstrap endpoint `/api/v1/session` возвращает current user, workspace,
membership/capabilities и CSRF token для header use. Session token остается
только в HttpOnly cookie и никогда не попадает в JavaScript.

Не отключать CSRF только потому, что API принимает JSON.

### 6.6 OpenAPI и TypeScript

FastAPI OpenAPI является machine-readable boundary. Frontend types/client
генерируются в контролируемом quality step.

Правила:

- generated types не редактируются вручную;
- generation deterministic и проверяется в CI;
- breaking response change требует обновления API contract tests;
- frontend feature может строить свой focused view model из generated DTO;
- generated DTO не передается бездумно через все component layers.

---

## 7. Владение состоянием

React не означает, что все состояние становится global.

| State | Владелец | Примеры |
| --- | --- | --- |
| Financial truth | FastAPI/application/database | operation type, confirmed status, balance, profit |
| Server state | route/feature data layer | operations list, review queue, reference options |
| URL state | React Router | filters, pagination, selected period, stable target |
| Form draft | form/feature component | amount input, selected category, unsaved description |
| Ephemeral row state | row/feature component | open panel, active review panel, request pending |
| App context | root shell | current user, workspace, role, theme |
| Durable preference | backend or explicit browser storage | theme after separate product decision |

Не хранить в global context:

- все fetched entities;
- drafts каждой закрытой строки;
- form field state всего приложения;
- derived financial totals;
- permission rules, которые должен проверять backend.

### 7.1 Mutation policy

Для financial mutations:

```text
submit
  -> локальный pending + aria-busy
  -> запрет конфликтующей повторной mutation той же сущности
  -> server command
  -> authoritative response
  -> focused cache update/invalidation
```

Не рисовать подтвержденный финансовый результат optimistically до ответа
server. Допустимы optimistic UI-only состояния: открытие панели, selected tab,
локальная подсветка working item.

`create`, `confirm`, `post` и `transfer` проходят отдельный idempotency audit.
Disabled button не является гарантией от повторного финансового результата.

### 7.2 Draft lifecycle

```text
close panel
  -> draft остается в mounted feature state;

cancel
  -> draft сбрасывается к последнему server snapshot;

422
  -> draft сохраняется, field errors привязаны к fields;

409
  -> draft сохраняется, показывается stale explanation и reload action;

success
  -> server snapshot заменяет entity, panel закрывается;

external entity refresh
  -> feature явно решает, сохранить draft или показать conflict.
```

---

## 8. Переносимый UX/UI контракт

### 8.1 Product personality

```text
calm
dense
precise
private
functional
trustworthy
distinctive
```

Интерфейс dark-first. Характер допускается в typography, copy, rhythm и
restrained accent details, но не конкурирует с деньгами, status и решением.

Избегать:

- gamification;
- generic AI wrapper language;
- corporate accounting bureaucracy;
- decorative brutality;
- nested boxes;
- одинаково ярких badges и buttons;
- больших hero-блоков внутри working screens;
- технических UUID, raw JSON и parser debug в обычном UI.

### 8.2 App shell

На любой authenticated page пользователь понимает:

```text
кто я
в каком workspace работаю
какая у меня роль
где находятся accounts, operations, imports и reports
```

Shell разделяет:

- current context: user, workspace, role;
- main work: dashboard, accounts, operations, imports, reports;
- reference data: categories, properties, rules;
- system/admin: profile, workspaces, integrations.

Primary global action зависит от capabilities и текущего workflow, но не
превращает header в набор конкурирующих CTA.

### 8.3 Money first

Порядок финансовой информации:

```text
amount + currency
financial meaning
date + description
category / property / accounts
status / source
technical implementation outside ordinary flow
```

Money использует tabular numbers; currency находится рядом и визуально слабее
amount. Negative value не растворяется в обычном тексте.

Semantic tones:

```text
income   -> green
expense  -> pink/red
transfer -> blue/sapphire
warning  -> yellow
danger   -> red
profit   -> purple
muted    -> secondary text/surface
```

Green не используется как универсальное selection состояние. Current/selected
context использует lavender/blue surface и дополнительный structural label.

### 8.4 Working screen

```text
PageHeader
  -> context/title/short explanation
  -> one main page action

PageSupport
  -> KPI/progress/problems
  -> secondary tools and collapsed filters

MainContent
  -> rows/table/report
  -> local empty/loading/error state
```

Один screen отвечает:

```text
где я?
что сейчас важно?
что требует решения?
какой следующий шаг?
```

### 8.4.1 Сохранение геометрии

React migration не является скрытым redesign. Baseline переносится из current
SSR и Frontend Next по наблюдаемому поведению и screenshots:

- app shell width, page gutters и вертикальный rhythm;
- плотность рабочих экранов;
- относительные колонки main/aside;
- положение amount, status, actions и expansion;
- размеры и alignment controls;
- desktop, `920px` и mobile transformations;
- focus, error и pending geometry без layout jumps.

Сохраняется perceptual geometry, а не каждый исторический пиксель. Разрешается
исправить overflow, broken wrapping, inconsistent spacing или accessibility
problem, но такое отличие фиксируется как намеренное. До удаления SSR для
ключевых состояний сохраняются side-by-side screenshots или equivalent visual
assertions.

Theme меняет palette и допустимые visual effects, но не layout geometry.
Если позже понадобится compact/comfortable density, это отдельная token axis,
а не побочный эффект темы.

### 8.5 Workbench Row

```text
WorkbenchRow
├── Main
│   ├── Header
│   ├── Description
│   ├── Meta
│   └── Signals
├── Aside
│   ├── Outcome
│   └── ActionStack
└── Expansion
```

Это layout component с composition slots, не универсальная financial entity.
Feature-owned components:

- `ReviewItem`;
- `ManualOperationRow`;
- `AccountMovementRow`;
- `CategoryRow`;
- `PropertyRow`;
- `TransactionRuleRow`.

Не создавать один `WorkbenchRowProps` с десятками `show*`, `is*` и optional
полей. Shared row владеет geometry и accessibility; feature владеет semantic
content, state и actions.

### 8.6 ActionStack

```text
Primary       максимум одно действие
Secondary     0-1 заметное вторичное действие
More          редкие действия
Danger zone   destructive actions отдельно
```

`Еще действия` — явный text action, не ellipsis-only icon. Dangerous action не
стоит рядом с save/apply как равная кнопка. Destructive action требует
подтверждения с понятным объектом и последствием.

### 8.7 States

Разделять:

| Канал | Пример | Presentation |
| --- | --- | --- |
| Financial meaning | income, expense, transfer | MoneyValue и semantic row accent |
| Durable status | confirmed, archived, ignored | calm metadata/badge |
| Problem | needs review, duplicate, mismatch, error | visible signal + explanation |
| Ephemeral UI | working, recent, target, focus | surface/outline/label |

Временный приоритет:

```text
working > target > recent
```

Focus не равен selection. Color не является единственным признаком. Temporary
highlight не скрывает financial or problem semantics.

### 8.8 Forms и expansion

Field groups идут по пользовательскому смыслу:

```text
primary        type / amount / date
classification accounts / category / property
details        description
footer         cancel / submit
```

Simple row correction использует expansion panel. Полноценный workflow
использует dedicated route или large feature panel, а не page form, вложенную в
card.

### 8.9 Feedback

- Mutation сохраняет working context.
- Local success не требует обязательного toast.
- Validation и network error находятся рядом с инициировавшей form/row.
- Background refresh не перехватывает focus.
- Created entity получает compact recent feedback и `Показать в списке`, без
  принудительной сортировки и scroll jump.
- Empty state объясняет не только отсутствие данных, но и следующий полезный
  шаг с учетом permissions.

### 8.10 Responsive и accessibility

Baseline viewports:

```text
desktop
920px control viewport
mobile around 390px
```

`920px` остается контрольной точкой совместимости первого пилота, но не
вечным hard-coded product requirement. Компоненты меняют layout по своему
реальному content pressure.

Обязательный baseline:

- native `button`, `a`, `input`, `select` semantics;
- visible `:focus-visible`;
- `aria-expanded` и `aria-controls` для disclosure;
- `aria-busy` для request scope;
- `role="alert"` для form-level error;
- `aria-describedby` для field error;
- focus первого invalid field;
- keyboard access;
- minimum interactive target около `44px`;
- `prefers-reduced-motion`;
- отсутствие unintended horizontal overflow;
- status не передается только цветом.

---

## 9. Shared и feature-owned components

### 9.1 Shared UI

```text
AppShell
PageHeader
PageActions
Button
IconButton
Badge
MoneyValue
Field
FormError
RequestState
EmptyState
KpiStrip
ActionStack
WorkbenchRow
ExpansionPanel
FilterDisclosure
PeriodNavigator
```

Shared component:

- не импортирует feature API;
- не выполняет financial mutation;
- не вычисляет permission;
- не знает backend status transitions;
- принимает small semantic props и composition children;
- имеет accessibility contract;
- использует semantic CSS tokens.

### 9.2 Feature UI

```text
manual-ledger/
  ManualLedgerPage
  ManualOperationRow
  ManualOperationForm

account-ledger/
  AccountHeader
  AccountMovementRow
  AccountFilters

import-review/
  ReviewQueue
  ReviewValidation
  ReviewItem
  ReviewPanelDeck
  CategoryPanel
  TransferPanel

import-mapping/
  MappingTablePicker
  ColumnMappingForm
  TransactionPreview

reports/
  ReportFilters
  ReportKpis
  CategoryReport
  PropertyReport

reference-data/
  CategoryRow
  PropertyRow
  TransactionRuleRow
```

`ReviewPanelDeck`, transfer matching, queue semantics и control totals не
поднимаются в shared UI.

### 9.3 CSS architecture

```text
frontend/app/app/styles/
  tokens.css
  themes/catppuccin-mocha.css
  themes/high-contrast.css       # когда появится продуктовая потребность
  foundation.css
  utilities.css

component/
  component.module.css
```

Token layers:

```text
reference values
  -> raw palette/font values внутри theme

semantic tokens
  -> --color-surface, --color-text, --color-income, --color-focus
  -> --space-*, --radius-*, --shadow-*, --motion-*
  -> --control-height-*, --page-gutter, --content-max-width

component CSS
  -> geometry и states через semantic tokens
```

Правила token/theme system:

- palette values живут только в theme files;
- theme подключается через один root attribute, например `data-theme`, без
  feature-specific theme branches;
- component не знает имя `catppuccin-mocha` и не использует raw palette token;
- component styles используют semantic tokens;
- repeated typography, spacing, radii, shadows, motion и control geometry имеют
  tokens;
- уникальное локальное значение не превращается автоматически в token: token
  выражает системное решение, а не скрывает каждое число;
- theme contract покрывает все semantic color tokens и проверяется отдельной
  development gallery или component test;
- новая theme добавляет values, а не копии component styles;
- theme не меняет layout, density и information hierarchy;
- отсутствие token fallback считается ошибкой, а не способом молча получить
  другой вид компонента.

Правила переиспользования и размера CSS:

- shared component является единственным владельцем своей повторяемой geometry;
- feature CSS описывает только feature composition и уникальные states;
- global CSS содержит reset, typography, shell primitives и documented
  utilities, но не feature pages;
- CSS Modules изолируют component/feature styles;
- utilities остаются маленьким закрытым набором и не превращаются во второй
  Tailwind, собранный вручную;
- одинаковые declarations сначала проверяются на общий смысл: только устойчивое
  решение поднимается в token или shared component;
- похожие, но семантически разные layouts не объединяются через десятки flags;
- CSS Module около `200–300` строк является сигналом проверить cohesion, а не
  механическим лимитом и не поводом дробить связную геометрию;
- общий line count не является самостоятельной целью: критерий — отсутствие
  дублирования, global leakage, specificity wars и неиспользуемых selectors;
- `!important` только для документированного infrastructure exception;
- не создавать compatibility aliases к legacy selectors;
- не переносить legacy `app.css` блоками в новый frontend;
- theme switcher не входит в первый pilot, theme contract входит.

---

## 10. Workflow contracts

### 10.1 Manual ledger — первый vertical pilot

Manual ledger выбран первым реализуемым workflow, потому что позволяет сравнить
одну задачу сразу в трех представлениях:

- working current SSR;
- изолированном Frontend Next;
- новом React/API adapter.

Он проверяет foundation на достаточно реалистичной сложности:

- JSON API, generated types, session/workspace и CSRF;
- list, filters, pagination и stable URL state;
- income/expense/transfer create and edit;
- lazy or on-demand edit data;
- server validation и сохранение client draft;
- cancel/restore/delete lifecycle;
- readonly mode и capabilities;
- `409` stale protection;
- focus, responsive layout и accessibility.

Сохраняются date, amount, currency, account/category/property filters и
server-owned financial meaning. Frontend Next manual implementation является
behavior и visual reference. Его Python Presenter, renderer, HTMX response code
и stylesheet целиком не переносятся.

Из Frontend Next CSS извлекаются только подтвержденные semantic tokens,
geometry, focus states, responsive rules и component-level visual decisions.
Они переписываются в React theme/global foundation и colocated CSS Modules без
legacy selectors и зависимости от Jinja DOM.

Pilot завершен, когда пользователь может выполнить полный manual workflow, а
current и Next manual implementations заменены тестами и удалены по
[`14.2`](#142-можно-удалить-после-react-manual-ledger-replacement).

### 10.2 Import review — complexity checkpoint

Import review выполняется вторым и является обязательным complexity checkpoint
перед массовой миграцией. Он проверяет именно ту сложность, ради которой
принимается React:

- queue progress;
- validation/control totals;
- uncertain classification;
- category and transfer panels;
- rules suggestions;
- possible duplicate and matching;
- sibling updates;
- local drafts and errors;
- stable working context;
- source traceability.

Checkpoint считается пройденным только если пользователь может закончить
реальный review workflow, а не увидеть read-only mock или одну React row внутри
Jinja. После него принимается окончательный go/no-go для массовой миграции
остальных complex workflows.

### 10.3 Account ledger

Account movement использует ту же row geometry, но передает две оси:

```text
operationType
entryDirection relative to selected account
```

Account header показывает balance and context; list не повторяет account в
каждом месте без пользовательской пользы.

### 10.4 Import mapping

Сохраняются:

- table candidate selection;
- column mapping;
- first data row and currency;
- preview before import;
- warnings and control totals;
- optional named mapping template;
- explicit separation setup from ledger posting.

Mapping не должен выглядеть как подтвержденная financial result page.

### 10.5 Reports

Сохраняются:

- quick month navigation;
- exact period and entity filters;
- income/expense/profit KPI;
- account balances;
- category/property comparisons;
- empty states, объясняющие зависимость от confirmed data;
- traceability обратно к operations/review.

Tables используются для сравнения, Workbench Rows — для решений и действий.

### 10.6 Reference and workspace screens

- Search появляется раньше сложной numbered pagination.
- Current workspace структурно отделен от other workspaces.
- Recent created entity не меняет сортировку списка.
- Edit использует expansion или dedicated surface.
- Readonly state объясняется.
- Member/invitation actions сохраняют least privilege и one-time secret rules.

---

## 11. Testing strategy

### 11.1 Сохраняем

- domain/financial tests;
- application use-case tests;
- repository/workspace isolation tests;
- parser/raw preservation/deduplication tests;
- realistic data builders из `scripts/ui_audit.py`;
- browser checks desktop/920/mobile;
- accessibility, focus и no-overflow discoveries;
- performance baseline query count/response size там, где он остается полезен.

### 11.2 Добавляем

```text
Backend
  API schema tests
  API auth/CSRF/error tests
  workspace isolation tests
  command idempotency/concurrency tests

Frontend
  pure formatter/policy tests
  component interaction tests
  route/feature integration tests with API stubs
  browser E2E against real FastAPI/PostgreSQL for critical flows
```

Critical browser flows:

- login/session expiration;
- workspace switching/isolation;
- manual income/expense/transfer;
- import upload/mapping/review/confirm;
- duplicate and control-total problem;
- report reflects confirmed operations and excludes transfer from profit;
- `409`, `422`, network error and retry;
- readonly user.

### 11.3 Не переносим как target tests

- exact full HTML snapshots;
- CSS class order assertions;
- Jinja macro rendering;
- `HX-Request` detection;
- OOB markers;
- `replaceRow`/`replaceList` HTML fragments;
- Alpine controller source-string assertions;
- internal implementation count без performance reason.

### 11.4 UI audit

`scripts/ui_audit.py` уже содержит valuable scenario seeding, screenshots и
responsive checks, но вырос до примерно `2 000` строк и знает legacy и Next CSS
selectors.

Миграционная стратегия:

1. Сохранить Python Playwright audit для manual-ledger React pilot.
2. Вынести reusable data seeding и browser assertions из monolithic script.
3. Добавить React routes как отдельный scenario, не ветвить каждый helper по
   `legacy/next/react`.
4. После workflow cutover удалить SSR-specific selectors и HTMX checks.
5. Перенос Playwright tests в TypeScript допускается позже, но не является
   условием первого React pilot.

---

## 12. Repository audit: что сохраняем

### 12.1 Безусловно сохраняем

```text
src/app/features/*/domain/
src/app/features/*/application/
src/app/features/*/repository.py
src/app/features/*/query_repository.py
src/app/features/*/models.py
src/app/features/*/mapping/        # кроме доказанно presentation-only mapping
src/app/features/*/infrastructure/
src/app/features/imports/parsing/
src/app/db/
src/app/core/security.py
src/app/features/workspaces/permissions.py
```

Сохраняются все financial invariants и tests независимо от frontend.

### 12.2 Сохраняем после адаптации

| Текущий код | Целевая роль |
| --- | --- |
| application DTO/read projections | источник API response mapper |
| service/use-case commands | вызываются API endpoints |
| workspace context/permission functions | основа API dependencies |
| session cookie helpers | same-origin auth |
| CSRF HMAC verification | header-based API CSRF |
| legacy presenters | временный источник wording/state discovery |
| Frontend Next MoneyFormatter | поведенческий baseline, не runtime dependency React |
| UI audit realistic scenario | backend + browser E2E fixture |
| semantic color/spacing tokens | первая React theme/foundation |

### 12.3 Не путать browser и chat presentation

`src/app/features/chat_integrations/presentation/` не является legacy browser
SSR. Chat rendering остается отдельным integration adapter и не удаляется при
React migration. Общие application services могут использоваться обоими
adapters.

---

## 13. Repository audit: что устарело или мешает

### 13.1 Critical: конфликтующие source-of-truth документы

Сейчас Jinja/HTMX как target продолжают объявлять:

- `AGENTS.md`;
- root `README.md`;
- `docs/README.md`;
- `docs/architecture/ARCHITECTURE.md`;
- `docs/design/FRONTEND_NEXT_DESIGN.md`;
- `docs/design/WORKBENCH_ROW_DESIGN.md`;
- `docs/design/DESIGN.md` в implementation-specific местах;
- `docs/product/ROADMAP.md`;
- ссылки из `PROJECT_VISION.md`, `DOMAIN_MODEL.md` и `MVP.md`.

Это главный организационный blocker. Пока инструкции противоречат друг другу,
новый агент может продолжить SSR migration и увеличить sunk cost.

Phase 0 обязан:

1. сделать этот документ первым frontend architecture reference;
2. обновить `AGENTS.md`, `README.md`, `docs/README.md` и `ARCHITECTURE.md`;
3. заменить Jinja-specific формулировки в active `DESIGN.md` на technology-neutral
   UX contracts;
4. пометить SSR migration docs как historical/superseded;
5. обновить roadmap.

### 13.2 Critical: нет JSON API adapter

Большинство browser routes одновременно:

- разбирают query/form input;
- вызывают service/use case;
- строят presenter context;
- выбирают full/HTMX response;
- возвращают redirect или Jinja.

React нельзя подключать к этим routes через HTML scraping или form emulation.
Нужен `src/app/api/v1` с отдельными schemas, dependencies и errors.

### 13.3 Critical: HTML-specific auth/CSRF behavior

`get_current_workspace_context` возвращает `303` login redirect и читает CSRF
из `request.form()`. Это несовместимо с predictable JSON API. Нужны API-specific
dependencies; существующий SSR contract сохраняется, пока его используют
legacy routes.

### 13.4 Important: две активные browser presentation systems

`src/app/main.py` одновременно:

- монтирует `/static` current frontend;
- монтирует `/_next/static`;
- подключает current feature routers;
- подключает `app.web.router`.

Добавление React без cleanup создает три frontend runtime. Поэтому
`src/app/web/` замораживается сейчас и удаляется после переноса его полезных
behavior contracts в React tests/docs.

### 13.5 Important: browser presentation внутри backend feature routers

Крупные файлы:

```text
src/app/features/ledger/router.py                 443 lines
src/app/features/accounts/router.py               426 lines
src/app/features/workspaces/router.py             416 lines
src/app/features/transaction_rules/router.py      393 lines
src/app/features/categories/router.py             364 lines
```

Не нужно рефакторить их в идеальный SSR перед React. При миграции workflow:

1. добавить API route поверх application use case;
2. оставить legacy route без новых presentation abstractions;
3. переключить canonical UI;
4. удалить legacy HTML route/presenter/template;
5. если в router остались non-browser endpoints, переименовать/split по роли.

### 13.6 Important: legacy CSS/JS coupling

`src/app/static/css/app.css`:

- `7 578` строк;
- `1 167` parsed rules;
- `773` unique class selectors;
- global, component и feature styles в одном cascade;
- HTMX/Alpine/DOM-shape dependencies;
- responsive overrides далеко от component definitions.

Его нельзя использовать как React foundation или постепенно импортировать в
React. Он frozen за исключением critical fixes и удаления migrated selectors.

Current JavaScript:

- `entity-target.js` знает selectors нескольких features;
- `import-review-scroll.js` компенсирует DOM replacement;
- vendor HTMX/Alpine нужны только SSR systems.

React воспроизводит user behavior, не эти механизмы.

### 13.7 Important: SSR-specific tests удерживают implementation

Template/presentation tests проверяют:

- Jinja output;
- CSS class names;
- HTMX attributes;
- OOB fragments;
- Alpine source hooks;
- exact partial boundaries.

Они полезны до cutover как characterization tests, но после replacement не
должны заставлять сохранять legacy HTML. Каждый workflow имеет test replacement
manifest.

### 13.8 Important: Frontend Next production code становится dead-end

После решения о React следующие части не должны расширяться:

```text
src/app/web/features/foundation/
src/app/web/features/ledger/manual/
src/app/web/ui/
src/app/web/templates/
src/app/web/static/
tests/ui_refactor/foundation/
tests/ui_refactor/contracts/
tests/ui_refactor/features/ledger/manual_next/
```

Полезное содержимое:

- money semantics;
- action hierarchy;
- error/draft lifecycle;
- focus/accessibility discoveries;
- optimistic concurrency;
- responsive behavior.

Оно переносится как API/component/E2E contracts, а не через Python reuse.

### 13.9 Suggestion: monolithic UI audit

`scripts/ui_audit.py` знает page registry, data setup, screenshots, selectors,
button audit и три frontend variants. Его следует разделить по reasons to
change, но только после manual-ledger pilot, чтобы не выполнять отдельный
tooling rewrite раньше продукта.

### 13.10 Не проблема репозитория: ignored cache files

В working tree могут существовать многочисленные `__pycache__` и `.pyc`. Они
игнорируются `.gitignore` и не отслеживаются Git. Их можно удалить локально для
чистоты, но они не являются architectural cleanup item и не должны смешиваться
с frontend migration commits.

---

## 14. Delete manifest и условия удаления

Удаление выполняется по потребителям, а не по сходству имен.

### 14.1 Можно удалить после React foundation baseline

| Target | Условие |
| --- | --- |
| ~~`/_next/foundation` route и `src/app/web/features/foundation/`~~ | удалено в React Stage 02 после visual/accessibility replacement baseline |
| Next foundation templates/tests | их устойчивые контракты заменены React component tests |
| Next-only foundation scenario в `ui_audit.py` | React foundation scenario существует |

### 14.2 Можно удалить после React manual-ledger replacement

| Target | Условие |
| --- | --- |
| `src/app/web/features/ledger/manual/` | React manual workflow и API прошли cutover |
| Next manual templates/CSS/JS consumers | replacement tests и browser audit проходят |
| `tests/ui_refactor/features/ledger/manual_next/` | API + React tests покрывают useful contracts |
| `tests/ui_refactor/features/ledger/manual/` baseline | владелец подтвердил replacement coverage |
| old `src/app/features/ledger/presentation/manual_operations/` | current SSR manual route также удален |
| `src/app/templates/ledger/manual*` | current SSR manual route удален |
| manual selectors из current `app.css` | поиск не показывает consumers |

### 14.3 Можно удалить после каждого legacy workflow cutover

```text
feature HTML routes and response renderers
browser-only presenters and ViewModels
feature Jinja templates and partials
feature-specific CSS selectors
feature-specific Alpine/JavaScript hooks
template/presentation tests без нового product value
legacy UI audit selectors
```

Удаление подтверждается:

1. `rg` по route/template/class/presenter names;
2. API/application/domain tests;
3. React feature tests;
4. browser E2E;
5. permission/workspace tests;
6. performance/no-overflow comparison;
7. отсутствие imports из chat or other adapters.

### 14.4 Можно удалить после последнего interactive SSR consumer

```text
src/app/web/ целиком
/_next/static mount
app.web.router include
src/app/static/js/vendor/htmx-*.js
src/app/static/js/vendor/alpine-*.js
src/app/static/js/entity-target.js
src/app/static/js/import-review-scroll.js
src/app/static/css/app.css
SSR-only templating helpers and icon registry
remaining interactive Jinja components
```

Public/auth SSR может временно сохранять Jinja без HTMX/Alpine. Полное удаление
`app.templating` выполняется только если home/login/signup/invitation flows также
перенесены или получили отдельный минимальный renderer.

### 14.5 Документы: archive, не production delete

После обновления active docs следующие документы помечаются historical и могут
быть перемещены в `docs/archive/frontend-ssr/`:

```text
docs/design/FRONTEND_NEXT_DESIGN.md
docs/design/WORKBENCH_ROW_DESIGN.md
docs/design/MANUAL_LEDGER_BASELINE.md
docs/design/REFACTOR_PROJECT_DESIGN.md
docs/css-audit.md
docs/review-item-css-migration-plan.md
```

Их не нужно удалять немедленно: они содержат behavior discoveries и audit data.
Но они не должны оставаться в active reading order или задавать новый backlog.

---

## 15. Миграционная стратегия

### Phase 0. Зафиксировать решение и остановить расхождение

- обновить active documentation и `AGENTS.md`;
- заморозить `src/app/web/` для новых feature;
- зафиксировать repository metrics и cleanup owners;
- применить принятые ADR для npm и single-container deployment integration;
- создать API error/auth/CSRF conventions;
- не удалять working current SSR.

### Phase 1. React и API foundation

- scaffold `frontend/`;
- создать `/app` shell и `/api/v1/session`;
- настроить same-origin dev proxy;
- добавить API `401/403/409/422` envelope;
- настроить OpenAPI type generation;
- перенести semantic tokens и Catppuccin Mocha theme;
- добавить минимальную test theme для проверки полноты semantic token contract;
- реализовать Button, Field, MoneyValue, RequestState, PageHeader;
- создать `frontend/README.md` и начало TypeScript-for-Python guide на примерах
  foundation-кода;
- зафиксировать screenshot geometry baseline current/Next manual ledger;
- добавить desktop/920/mobile smoke;
- `/_next/foundation` удалён после replacement baseline в React Stage 02.

### Phase 2. Первый vertical pilot: manual ledger

- описать API schemas поверх existing manual-ledger application services;
- реализовать list, filters и full create/edit lifecycle в React;
- проверить income/expense/transfer semantics, workspace и readonly;
- проверить validation drafts, `409`, focus и responsive behavior;
- перенести проверенные semantic tokens и component rules из Frontend Next CSS,
  не подключая его stylesheet целиком;
- сравнить current SSR, Frontend Next и React на realistic scenario;
- переключить canonical manual route после observation stage;
- удалить оба manual SSR implementations по delete manifest.

Exit criteria:

- API foundation доказан реальной unsafe financial mutation;
- financial semantics остаются server-owned;
- полный workflow проще читать и тестировать, чем два SSR equivalents;
- replacement tests позволяют удалить current и Next manual presentation;
- CSS foundation не зависит от legacy/Next DOM и selectors.

### Phase 3. Complexity checkpoint: import review

- описать API schemas вокруг existing import application use cases;
- реализовать полный review route в React;
- проверить queue, validation, panels, errors, matching, sibling updates;
- проверить workspace/readonly/idempotency;
- сравнить production complexity и developer ergonomics с legacy/Next;
- принять окончательный go/no-go перед массовой migration.

Go criteria:

- financial semantics остаются server-owned;
- workflow проще читать и тестировать, чем HTMX/OOB equivalent;
- нет нового generic state framework без необходимости;
- API schemas не дублируют domain rules;
- focus, errors, draft и responsive baseline работают;
- performance приемлема на realistic document.

### Phase 4. Core financial workflows

Рекомендуемый порядок после успешного complexity checkpoint:

1. account detail/ledger;
2. import documents and mapping;
3. reports.

### Phase 5. Reference/admin workflows

1. properties;
2. categories;
3. transaction rules;
4. workspaces/members/invitations;
5. profile and remaining authenticated pages.

### Phase 6. Final SSR cleanup

- удалить последний authenticated legacy presentation;
- удалить `src/app/web/` и `/_next` mount;
- удалить HTMX/Alpine/vendor scripts без consumers;
- удалить current CSS/templates/presenters без consumers;
- очистить UI audit branches;
- архивировать SSR migration docs;
- решить, остаются ли public/auth routes minimal SSR или переходят в React;
- вернуть canonical product URLs.

---

## 16. Правила вертикального cutover

Каждый workflow проходит один цикл:

```text
inventory behavior and consumers
-> define API contract
-> implement React workflow
-> add replacement tests
-> compare security/financial behavior
-> switch canonical navigation
-> observe
-> delete superseded presentation
-> search for leftovers
```

Запрещено:

- добавлять `if react_ui` в legacy presenter/template;
- вызывать legacy HTTP route из API route;
- использовать Jinja ViewModel как JSON schema;
- возвращать HTML внутри JSON для React;
- загружать legacy CSS в React;
- держать migrated workflow постоянно в двух authenticated UI;
- создавать `*_old.py`, `*_legacy.tsx` или закомментированные копии;
- удалять application/domain tests вместе с presentation tests.

Временный legacy route допускается на один оговоренный observation stage с
явной датой/условием удаления.

---

## 17. Risks и mitigations

| Риск | Mitigation |
| --- | --- |
| Три frontend во время миграции | freeze Next, manual pilot, immediate vertical cleanup gates |
| Дублирование financial logic в TypeScript | semantic API fields, server authority, backend tests |
| API превращается в UI-specific BFF schemas | resource/workflow schemas без component placement |
| Слишком ранний frontend framework zoo | minimal dependencies, ADR only after real need |
| Потеря SSR progressive enhancement | reliable errors/retry/deep links; legacy remains до replacement |
| Session/CSRF regression | same-origin, HttpOnly cookie, API CSRF header tests |
| Workspace leak | API dependency + scoped repository tests on every resource family |
| Optimistic UI показывает ложные деньги | no optimistic financial confirmation |
| Long migration preserves dead code | vertical cleanup manifest and consumer search |
| UI audit rewrite съест migration budget | reuse Python Playwright first, split later |
| React component becomes universal CRUD | composition slots, feature ownership, no flag-heavy models |
| Generated API types leak everywhere | feature mapping at API boundary |
| Новый frontend непонятен владельцу проекта | explicit code, Python-oriented learning docs, concept walkthrough per slice |
| Token system разрастается в свалку variables | semantic layers, named ownership, no token per arbitrary value |
| Сохранение geometry превращается в перенос старых bugs | screenshot baseline плюс documented intentional differences |

---

## 18. Quality gates

Backend:

```text
uv run ruff format --check .
uv run ruff check .
uv run ty check
uv run pytest
```

Frontend commands фиксируются после scaffold и должны включать:

```text
format check
lint
TypeScript check
unit/component tests
production build
critical browser E2E
```

Для каждого migrated workflow:

- workspace isolation;
- permissions/readonly;
- financial invariants;
- API schema/error contract;
- stale `409` при editable entity;
- critical mutation idempotency audit;
- loading/empty/error/success;
- keyboard and focus;
- desktop/920/mobile;
- no unintended overflow;
- side-by-side geometry review для ключевых состояний до SSR cleanup;
- отсутствие raw palette values в component/feature CSS;
- используемая theme определяет полный semantic token contract;
- shared styles не продублированы внутри feature без причины;
- нет необоснованных `any`, type assertions и effects для derived state;
- новый TS/React concept объяснен в handoff или focused learning doc;
- browser console/request errors;
- cleanup manifest выполнен после observation stage.

---

## 19. Definition of Done всей миграции

1. Authenticated financial application работает через React и versioned API.
2. FastAPI остается единственным backend и владельцем financial truth.
3. React не импортирует и не воспроизводит domain rules.
4. API имеет JSON auth, CSRF, error, version и workspace contracts.
5. Manual ledger, import review, account ledger, mapping и reports прошли
   realistic E2E.
6. Transfers не влияют на profit во всех UI projections.
7. Raw import data и traceability сохранены.
8. Current SSR не остается вторым постоянным authenticated frontend.
9. `src/app/web/`, `/_next` routes/static и Next-only tests удалены.
10. Legacy HTML routes, presenters, templates, CSS и JS удалены после последнего
    consumer либо явно ограничены public/auth SSR.
11. HTMX и Alpine удалены, если нет оставшегося доказанного consumer.
12. Active docs и `AGENTS.md` описывают фактическую React/API архитектуру.
13. Historical SSR docs находятся вне active reading order.
14. UI audit не содержит ветвей для удаленных frontend.
15. Domain/application/repository tests продолжают проходить.
16. React build, type check, lint, tests и browser audit проходят.
17. Repository не содержит production-копий `old`, `legacy` или `next` без
    оставшегося runtime consumer.
18. Компоненты используют semantic tokens, минимум одна дополнительная test
    theme подтверждает полноту theme contract без копирования component CSS.
19. Геометрия ключевых экранов сохранена либо изменения явно приняты как UX fix.
20. `frontend/README.md` и TypeScript-for-Python guide объясняют реальный project
    flow, а не только команды package manager.
21. Владелец проекта может проследить API request, state transition и render
    manual-ledger workflow по коду и сопроводительной документации.

---

## 20. Реестр решений

1. React — target authenticated frontend.
2. FastAPI остается единственным backend.
3. React frontend живет в top-level `frontend/`.
4. JSON API живет в `src/app/api/v1/`.
5. Начальный rendering mode — React Router SPA mode.
6. Deployment same-origin; permissive CORS не используется как shortcut.
7. Session остается HttpOnly cookie; CSRF передается отдельным header.
8. API возвращает capabilities, а не server-owned button placement.
9. Money передается decimal string + currency + server-owned semantic fields.
10. Financial mutations не показывают optimistic confirmed result.
11. Global client state не вводится без доказанной cross-feature задачи.
12. Shared UI использует composition; feature сохраняет workflow ownership.
13. Semantic tokens и Catppuccin Mocha переносятся, legacy CSS — нет.
14. Manual ledger является первым React vertical pilot.
15. Import review является обязательным complexity checkpoint перед массовой
    миграцией.
16. Frontend Next замораживается и удаляется после replacement contracts.
17. Legacy удаляется вертикально после cutover, не big-bang заранее.
18. Existing Python Playwright audit переиспользуется на первом этапе.
19. Public/auth SSR может временно остаться отдельной минимальной поверхностью.
20. CSS строится на semantic tokens; themes заменяют token values и не копируют
    component styles.
21. Geometry current UI сохраняется как migration baseline; redesign отделен от
    framework rewrite.
22. TypeScript/React код оптимизируется для явности и обучения Python-разработчика,
    не для демонстрации framework tricks.
