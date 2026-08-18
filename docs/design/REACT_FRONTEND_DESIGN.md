# React Frontend Architecture

Статус: активная целевая архитектура browser frontend.

Принятые причины решения зафиксированы в
[`architecture/decisions`](../architecture/decisions/README.md), текущая
последовательность — в [`frontend plan`](../frontend/plan/README.md).

## Решение

Booker Tee использует один React SPA для всего browser frontend и FastAPI как
единственный backend.

```text
React route
  -> typed API client
  -> /api/v1
  -> application use case/query
  -> domain/repository
```

Jinja/HTMX/Alpine presentation stack удалён и не должен восстанавливаться.

## Current state

Каноничны в React:

- `/app` (Dashboard);
- `/app/operations` (`/app/ledger/manual` — compatibility redirect);
- `/app/accounts`;
- `/app/accounts/:accountId`;
- `/app/debts`;
- `/app/debts/:debtId`;
- `/app/imports`;
- `/app/imports/upload`;
- `/app/imports/documents/:documentId`;
- `/app/imports/documents/:documentId/mapping`;
- `/app/imports/documents/:documentId/review`;
- `/app/reports`;
- `/app/properties`;
- `/app/categories`;
- `/app/categories/:categoryId`;
- `/app/rules`;
- `/app/workspaces`;
- `/app/workspaces/:workspaceId/activity`;
- `/app/workspaces/invitations/:invitationToken`;
- `/app/chat-integrations/telegram/dev-link` в local/test окружении;
- `/app/profile` и `/app/profile/sessions`;
- `/app/auth/login` и `/app/auth/signup`;
- shared shell/foundation/themes.

Все product, public invitation и auth pages каноничны в React. `/` направляет в
React SPA; локальная chat integration page остаётся development-only surface.

## Runtime and deployment

```text
/app/*    React SPA fallback
/assets/* immutable React build assets
/api/v1/* FastAPI JSON
/         redirect to React SPA
/...      historical GET redirects + provider webhooks
```

- `react_frontend.py` раздаёт SPA и assets;
- `legacy_frontend_redirects.py` временно хранит явные GET redirects со старых
  browser routes на канонические React routes;
- React dev server proxy обращается к FastAPI.
- Production build раздаётся FastAPI в same-origin deployment.
- Короткий access JWT хранится только в памяти React и передаётся как Bearer.
- Ротируемый refresh JWT хранится в scoped `HttpOnly` cookie; server-side
  `UserSession` сохраняет немедленный отзыв и управление устройствами.
- Security middleware проверяет host/origin/session.
- CORS не открывается широко.

`/app` prefix осознанно сохранён. Его можно удалить отдельным routing cutover;
до этого historical product GET routes используют query-preserving redirects.

## Frontend structure

```text
frontend/app/
  api/
    generated/       generated OpenAPI types
    transport.ts     common fetch/error boundary
  routes/            React Router adapters/loaders
  features/          domain-specific UI/state
  ui/                stable shared components
  shell/             authenticated navigation
  session/           session/workspace boundary
  shared/            small date/money primitives
  styles/
    tokens.css
    themes/
    foundation.css
```

Routes are thin. Feature code не импортирует внутренности другой feature.
Shared UI не знает API и business transitions.

## API boundary

### Contracts

- Server Pydantic schemas — wire contract.
- OpenAPI генерирует TypeScript shape.
- Runtime validation используется на network boundary для critical responses.
- Handwritten feature models не редактируют generated types.
- Money — decimal string; date/time — ISO; identity — UUID string.

### Capabilities

Backend возвращает facts:

```json
{
  "canEdit": false,
  "canDelete": false,
  "blockingReasonCode": "linked_operation"
}
```

Frontend выбирает copy, icon, layout и target route. Он не выводит permission
или financial rule из status.

### Errors

Используются стабильные классы:

- `401` unauthenticated;
- `403` authenticated без capability;
- `404` недоступная/несуществующая workspace entity;
- `409` stale state, idempotency conflict или недопустимый transition;
- `422` field/command validation;
- `5xx` unexpected failure без private details.

Error response имеет stable code, message и optional field errors. Draft не
теряется при ожидаемой server validation.

Повторяющиеся frontend-типы и constructors для network, `401`, `403` и generic
mutation errors находятся в `app/api/failures.ts`. Feature API сохраняет рядом с
workflow обработку `404`, `409`, `422`, blocker codes, fallback copy и runtime
validation успешного ответа. Общий слой не выбирает доменный transition и не
скрывает порядок обработки feature-specific статусов.

Loader-запросы возвращают `unauthenticated`, чтобы route мог показать стабильное
состояние входа. Browser mutation handlers используют общий
`session/unauthenticated.ts`: он перенаправляет только для `401` и сохраняет
`pathname + search + hash` в параметре `next`. Feature-код не собирает login URL
и не вызывает `window.location.assign` самостоятельно. `403` остаётся локальной
ошибкой capability и никогда не превращается в login redirect.

Collection routes с одинаковым контрактом `unauthenticated | error` используют
`session/authenticated-route-state-page.tsx` поверх общего `RouteStatePage`.
Detail и document workflows оставляют локальную композицию, когда их
`forbidden`, `notFound`, copy или recovery action действительно различаются.

### Mutations

- Финансовые mutations не optimistic.
- UI-only disclosure/selection может быть optimistic.
- Pending предотвращает повторную submit.
- Retry-sensitive command имеет idempotency/replay contract.
- Response содержит smallest truthful committed consistency set.
- После mutation не выполняется серия хрупких client-side догадок.

## State ownership

### URL

Хранит navigation context:

- route identity;
- filter/sort/page;
- выбранную строку или количество раскрытых rows, если Back/Forward должен это
  восстанавливать.

### Loader/server state

Хранит API snapshots. Без доказанной необходимости не добавляется global cache
library.

### Feature-local state

- active panel/disclosure;
- form draft;
- focus/confirmation;
- transient pending/error;
- выбранная mapping table.

### Server only

- financial truth;
- permissions/capabilities;
- lifecycle;
- dedupe;
- transfer direction/validity;
- confirmability и blocking reasons.

## Styling

- Semantic tokens и theme files.
- Component CSS Modules.
- Feature module может композировать shared primitives.
- Legacy CSS не импортируется.
- Global React CSS ограничен reset/foundation/app geometry.
- Inline palette values допустимы только в token/theme definitions.
- Class naming внутри module может быть Pascal/camel по локальному соглашению;
  filenames остаются kebab-case, component symbols — PascalCase.

## Components

Поднимать component в `ui/` только после устойчивого повторения. Уже существуют:

- buttons, icon, status primitives;
- fields/form layout/error summary;
- money value;
- page frame/header/request state/route state/loading page;
- expansion and confirmation;
- workbench surface/header;
- workbench toolbar/search;
- applied filter summary;
- responsive record collection;
- workbench filter/status/content regions;
- workbench row/panel;
- searchable select и action stack.

Не создавать universal CRUD page, generic financial row schema или form
generator.

## Forms and accessibility

Следовать [`FORM_DESIGN.md`](FORM_DESIGN.md):

- controlled draft там, где есть cross-field logic;
- native controls по умолчанию;
- error summary + field errors;
- focus first invalid field;
- accessible dialog/disclosure;
- reduced motion;
- status text независимо от цвета.

## Workflow contracts

### Manual Ledger

React владеет list/filter/draft UI. API/application владеет create/update,
cancel/restore/delete, optimistic version и transfer invariants.

### Import Review

React владеет queue navigation, panels и drafts. Server владеет validation,
classification facts, duplicate evidence, transfers, rule application,
posting, lifecycle и authoritative reconciliation.

### Import documents and mapping

План:
[`import-documents-and-mapping`](../frontend/plan/import-documents-and-mapping/README.md).

Ключевые ограничения:

- upload сохраняет source до parse;
- `storage_key` не публикуется;
- raw text/tables bounded и lazy;
- mapping preview server-side;
- mapping import создаёт reviewable rows и идемпотентен;
- конечный шаг — существующий React Import Review.

### Accounts and account ledger

Действующий feature contract:
[`frontend/app/features/accounts/README.md`](../../frontend/app/features/accounts/README.md).

Ключевые ограничения:

- list использует focused aggregate projection без per-account ledger N+1;
- balance остается server-owned и учитывает только confirmed entries;
- filters/pagination принадлежат URL, account/settings drafts — feature state;
- detail reads не seed-ят categories и не выполняют commit;
- account mutations имеют explicit stale-state guard;
- imported correction переиспользует optimistic operation version и меняет
  только разрешенные review fields.

### Transaction Rules

Действующие contracts:

- [`frontend/app/features/transaction-rules/README.md`](../../frontend/app/features/transaction-rules/README.md) —
  React route, state и interaction ownership;
- [`src/app/features/transaction_rules/README.md`](../../src/app/features/transaction_rules/README.md) —
  application/domain, non-browser consumers и financial boundaries.

Ключевые ограничения:

- rule только предлагает/prefill-ит Import Review и не подтверждает ledger;
- URL владеет directory filters/pagination, local state — drawer, один inline
  editor и confirmations;
- workspace access, references, capabilities и concurrency принадлежат server;
- create идемпотентен, lifecycle влияет на future matching, hard delete
  разрешён только disabled и directly unreferenced rule;
- create открывается справа, edit раскрывается под выбранной записью.

### Public and integration workflows

Workspace invitation preview/accept использует privacy-safe public read API и
authenticated CSRF-protected accept API. Telegram dev-link доступен только в
local/test; production API возвращает `404`. Provider webhook остаётся FastAPI
integration adapter, а не browser page.

## Vertical migration

```text
1. Observe current behavior and geometry.
2. Define typed application/API boundary.
3. Implement route state and UI.
4. Cover server authority and React interactions.
5. Run realistic browser flow.
6. Switch canonical navigation.
7. Delete legacy routes/templates/presenters/assets/tests.
```

Нельзя:

- вызывать HTML route из API;
- сериализовать legacy ViewModel;
- переносить ORM object в browser contract;
- оставлять две mutation surfaces после cutover;
- считать redirect полноценным cleanup;
- переписывать domain/application ради удобства JSX.

## Testing and gates

Backend:

- application/domain;
- workspace isolation;
- API auth/schema/error;
- idempotency/concurrency;
- no side effects in reads.

Frontend:

- runtime schema;
- route loader/action;
- state/draft/error;
- keyboard/focus/accessibility;
- formatting and build.

Browser:

- realistic workflow;
- desktop `1440`, tablet `920`, mobile `390`;
- deep links, reload, Back/Forward и historical redirects;
- no overflow, console/page/request errors.

## Final definition of done

- React — единственный browser frontend.
- FastAPI — единственный backend.
- Jinja/HTMX/Alpine и legacy CSS удалены.
- Public/auth presentation работает в том же React SPA.
- `/app` routing cutover осознанно отложен.
- Financial/security rules остались server-owned.
- Документация описывает текущий код, а завершённые migration journals удалены.
