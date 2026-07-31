# React Frontend Architecture

Статус: активная целевая архитектура browser frontend.

Принятые причины решения зафиксированы в
[`architecture/decisions`](../architecture/decisions/README.md), текущая
последовательность — в [`frontend plan`](../frontend/plan/README.md).

## Решение

Booker Tee использует один React SPA для authenticated financial application и
FastAPI как единственный backend.

```text
React route
  -> typed API client
  -> /api/v1
  -> application use case/query
  -> domain/repository
```

Legacy Jinja/HTMX остаётся только у ещё не мигрированных workflows. Новый
authenticated workflow в legacy stack не добавляется.

## Current state

Каноничны в React:

- `/app/ledger/manual`;
- `/app/accounts` — список и создание;
- `/app/imports`;
- `/app/imports/upload`;
- `/app/imports/documents/:documentId`;
- `/app/imports/documents/:documentId/mapping`;
- `/app/imports/documents/:documentId/review`;
- shared shell/foundation/themes.

Account detail/management и остальные authenticated pages пока SSR и мигрируют
Stage 7. Текущий workflow:
[`accounts and account ledger`](../frontend/plan/accounts-and-ledger/README.md).
Public home, login/signup могут оставаться минимальным SSR после financial
cutover — это отдельное решение.

## Runtime and deployment

```text
/app/*    React SPA fallback
/assets/* immutable React build assets
/api/v1/* FastAPI JSON
/...      public/auth + remaining legacy routes
```

- `react_frontend.py` раздаёт SPA и assets;
- `legacy_frontend_redirects.py` временно хранит явные GET redirects со старых
  browser routes на канонические React routes;
- React dev server proxy обращается к FastAPI.
- Production build раздаётся FastAPI в same-origin deployment.
- Cookie session остаётся backend-owned.
- Security middleware проверяет host/origin/session.
- CORS не открывается широко.

После полной authenticated migration `/app` prefix можно удалить отдельным
routing cutover. До этого historical product GET routes используют
query-preserving redirects только после replacement gate.

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
- page frame/header/request state;
- expansion and confirmation;
- workbench surface/header;
- workbench toolbar/search;
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

План:
[`accounts-and-ledger`](../frontend/plan/accounts-and-ledger/README.md).

Ключевые ограничения:

- list использует focused aggregate projection без per-account ledger N+1;
- balance остается server-owned и учитывает только confirmed entries;
- filters/pagination принадлежат URL, account/settings drafts — feature state;
- detail reads не seed-ят categories и не выполняют commit;
- account mutations имеют explicit stale-state guard;
- imported correction переиспользует optimistic operation version и меняет
  только разрешенные review fields.

### Remaining workflows

Reports, reference data и administration получают собственный
inventory/API/state/delete manifest до production implementation.

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

- React — единственный authenticated financial frontend.
- FastAPI — единственный backend.
- Legacy authenticated Jinja/HTMX/Alpine и CSS удалены.
- Public/auth presentation имеет явное решение.
- `/app` routing cutover выполнен или осознанно отложен.
- Financial/security rules остались server-owned.
- Документация описывает текущий код, а завершённые migration journals удалены.
