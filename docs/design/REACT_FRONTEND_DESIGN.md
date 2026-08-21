# React frontend architecture

Статус: действующая browser architecture.

Booker Tee использует один React Router SPA и FastAPI как единственный backend и
session owner.

```text
React route -> typed API client -> /api/v1 -> application use case/query
            -> domain/repository -> PostgreSQL
```

Jinja/HTMX/Alpine presentation stack удалён и не возвращается. Historical GET
routes могут выполнять query-preserving redirect в React до отдельного routing
cutover; legacy mutations не сохраняются.

## Runtime

```text
/app/*    React SPA
/api/v1/* FastAPI JSON API
/         redirect to React
```

Production использует same-origin proxy. CORS не заменяет правильный deployment.
FastAPI владеет authentication, session, CSRF и workspace context.

## Frontend boundaries

- `app/routes/`: URL parsing, loaders/actions and route-level composition.
- `app/features/`: feature state, mappers and UI.
- `app/ui/`: proven shared components without financial policy.
- `app/styles/`: semantic tokens, themes and foundation.
- `app/api/`: transport client and generated schema.
- `app/session/`: authenticated session/capability state.
- `app/shell/`: navigation and workspace context.

Routes remain thin. A feature owns its server DTO → UI model mapping, draft,
mutation state and feature-specific layout.

## API boundary

Versioned JSON routers live in `src/app/api/v1` and call application use
cases/readers directly. They do not call browser redirects or serialize ORM.
Pydantic response schemas own the wire contract.

Generated TypeScript types represent transport only. Feature models may narrow
or reshape them, but must handle unknown/optional values explicitly. Runtime
validation is used only at trust boundaries that need it, not for every internal
object.

Backend returns:

- formatted or exact money/currency values;
- status and financial outcome;
- action capabilities;
- stable error code and field errors;
- optimistic version/pagination metadata;
- privacy-safe references.

React does not derive permission, duplicate policy, transfer direction,
confirmation readiness or profit behavior from raw fields.

## State

- URL owns shareable filters, period, page and selected identity.
- Loader owns initial server state.
- Component owns ephemeral draft, expansion and pending action.
- Server owns financial truth and durable workflow state.
- Query/mutation helpers remain feature-local until a repeated contract exists.

On conflict, keep the user's draft when safe, show the server outcome and offer
reload/retry. Idempotency keys are stable across a retry of the same intent and
change for a new intent.

## Styling and composition

Use semantic CSS variables, themes and CSS Modules. Shared component CSS owns
its internals; feature CSS owns unique layout. Do not add Tailwind/shadcn,
runtime CSS-in-JS or a second theme system.

Select components through [`UI_FOUNDATION.md`](UI_FOUNDATION.md). Prefer native
controls and platform behavior. Accessibility and responsive rules live in
[`DESIGN.md`](DESIGN.md).

## Testing

For a changed workflow, use the smallest relevant set:

- backend domain/application tests for financial/security rules;
- API tests for auth, schema and stable errors;
- feature tests for DTO mapping, URL state and mutation outcomes;
- browser audit for critical end-to-end, focus and responsive behavior;
- generated API contract check when schemas change.

A browser feature is complete only when the API is authoritative, historical
GET compatibility is explicit, no second presentation implementation exists and
privacy/workspace/financial invariants remain covered.
