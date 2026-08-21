# Booker Tee Architecture

Статус: активный архитектурный справочник.

## Stack

- Python 3.12+, FastAPI;
- SQLAlchemy 2 async, Alembic, PostgreSQL;
- Pydantic v2;
- React 19, TypeScript strict, React Router Framework Mode в SPA mode;
- versioned same-origin JSON API;
- semantic CSS tokens, themes и CSS Modules;
- local PDF/XLSX extraction;
- uv, Ruff, ty, pytest, npm, ESLint, Prettier, Vitest, Playwright.

Нельзя добавлять новый framework/backend/storage/queue/AI stack без отдельного
решения.

## Runtime

```text
/app/*    -> React SPA
/api/v1/* -> FastAPI JSON API
/         -> redirect to React SPA
/...      -> historical GET redirects and provider webhooks
```

FastAPI остаётся единственным business backend и session owner. Production
same-origin: permissive CORS не используется как замена правильному deployment.

React каноничен для всех browser workflows. Временный `/app` prefix сохранён до
отдельного routing cutover; исторические GET URL перенаправляют в React.

## Repository boundaries

```text
frontend/
  app/routes/       route adapters
  app/features/     feature UI and state
  app/ui/           proven shared UI
  app/styles/       tokens, themes, foundation
  app/api/          transport and generated schema

src/app/
  api/v1/           JSON presentation adapter
  features/         application/domain/persistence + integration adapters
  core/             settings, middleware, security
  db/               database foundation
  shared/           narrow stable server concepts
```

Generated files отделены от handwritten code. `frontend/app/api/generated` не
редактируется вручную.

## Progressive feature architecture

Простая feature:

```text
feature/
  models.py
  repository.py
  service.py
  router.py
```

Сложная feature растёт по ответственности:

```text
feature/
  routes/
  application/
  domain/
  presentation/
  mapping/
  infrastructure/
```

Не создавать папки или abstractions только ради симметрии.

## Layers

### Router / API adapter

- HTTP schemas, dependencies, auth/permission, status codes;
- перевод request в application command;
- перевод application DTO в response;
- без SQL и financial calculations.

### Application

- orchestration workflow;
- transaction boundary;
- coordination repositories/domain/infrastructure;
- typed commands, results и read projections.

### Domain

- pure policies, status transitions, validation, calculations;
- без FastAPI, ORM session, templates и browser concepts.

### Repository

- только queries/persistence;
- workspace filters видимы;
- не принимает решений о UI или business workflow.

### Persistence models

- database shape, relationships, indexes и constraints;
- без orchestration.

### Presentation

- React;
- labels, formatting, layout, focus и local draft;
- не определяет permission, transfer semantics, dedupe или confirmability.

### Infrastructure

- files, extractors и provider clients;
- безопасные errors/logging;
- не подтверждает ledger records.

## Main flows

```text
React -> API router -> application -> repository/domain -> database
chat  -> provider adapter -> application -> same domain/repositories
```

Chat не является альтернативной ledger implementation.

## Transactions

- Application use case владеет commit/rollback.
- Financial mutation атомарна.
- HTTP route не делает серию несвязанных commits.
- Reads side-effect free.
- Длительный import может фиксировать сохранённый document и отдельные
  `ParseAttempt`, но обязан сохранять трассируемое состояние при failure.
- Retry-sensitive mutations используют idempotency key/fingerprint или другой
  явно проверенный replay contract.
- Optimistic concurrency применяется к редактируемым confirmed operations.

## Workspace security

```python
select(Entity).where(
    Entity.id == entity_id,
    Entity.workspace_id == workspace_id,
)
```

- Нельзя доверять `workspace_id` из формы.
- Parent ownership проверяется до child lookup.
- Viewer/manager capabilities рассчитывает server.
- Not-found/forbidden responses не должны раскрывать существование чужих данных.
- Chat integration соблюдает те же границы.

## API conventions

- Prefix `/api/v1`.
- Pydantic request/response schemas.
- UUID и ISO date/time в JSON.
- Money передаётся decimal string, не binary float.
- Stable error envelope и reason codes.
- Capabilities передают допустимость действий; URLs, labels и tones строит UI.
- OpenAPI генерирует TypeScript contract; runtime validation защищает network
  boundary там, где это требуется.
- Mutation возвращает smallest truthful committed snapshot.
- Main DTO не включает storage paths, secrets и неограниченный raw payload.

## Data models

Pydantic v2 является стандартным способом описания типизированных данных
приложения:

- commands, DTO, read models, query projections и use-case results;
- parser input/output и integration messages;
- persisted JSON/JSONB contracts;
- API request/response schemas.

Внутренние модели наследуют общий immutable `ApplicationModel`. API-схемы
наследуют `ApiModel` и отдельно определяют HTTP/OpenAPI contract. Одинаковая
структура переводится на границе напрямую:

```python
return DocumentApiResponse.model_validate(document)
```

Отдельный mapper создаётся только для реального семантического преобразования,
а не для перекладывания одноимённых полей.

`dataclass` остаётся допустимым для runtime-композиции: контейнеров
зависимостей, настроенных handlers/adapters и другого технического состояния,
которое не валидируется, не сериализуется и не передаётся как application
data. Actor с поведением остаётся обычным named class; SQL persistence —
SQLAlchemy model; фиксированный набор значений — `Enum`/`StrEnum`.

## Imports

```text
store document
  -> ParseAttempt
  -> extract
  -> parser or mapping
  -> RawTransaction
  -> validation/dedupe/review
  -> Operation + MoneyEntry
```

Parser registry и extractors — infrastructure/application collaborators.
Application гарантирует сохранение source, attempts и review-first. Подробные
инварианты находятся в [`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md).

## Code readability

- Explicit imports from defining modules.
- Named actors для workflow: `StatementUploadUseCase`,
  `ManualOperationService`, `ImportReviewReader`.
- Pure small helpers остаются функциями.
- Не использовать broad `utils.py`, wildcard exports и import side effects.
- 250–350 строк — сигнал cohesion review; 500+ handwritten lines требуют
  явного объяснения.
- Shared abstraction появляется после повторного устойчивого контракта.

## Frontend runtime

Все browser workflows каноничны в React. Historical GET routes могут сохранять
query-preserving redirects до общего routing cutover; старые mutation routes,
templates и presenters не возвращаются. Новый workflow проходит через
application/API boundary, typed React state, tests и browser evidence.

## Testing

Приоритет:

- financial invariants и status transitions;
- workspace isolation;
- import source/failure preservation;
- dedupe/idempotency;
- API auth/schema/error contracts;
- React state, forms, focus и accessibility;
- realistic browser flow на desktop/tablet/mobile.

Test должен закреплять поведение владельца правила. Template snapshot не
заменяет application test.

## Privacy and operations

- Не логировать raw statements, account numbers, tokens и secrets.
- External document/AI services требуют явного product decision.
- Upload storage и database backup рассматриваются вместе.
- Alembic обязателен для schema changes.
- Background queue вводится только после измеренной необходимости.

## Quality gates

```text
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest

cd frontend
npm run check
```
