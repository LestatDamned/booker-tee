# Stage 01: Runtime And API Foundation

Status: completed 2026-07-20.

## Goal

Получить минимальный production-shaped React/FastAPI контур: frontend запускается
и собирается, browser получает session/workspace context через JSON, а unsafe API
имеет корректный CSRF и error contract.

## User-Visible Outcome

Authenticated пользователь открывает `/app`, видит минимальный shell с current
user/workspace и получает понятные loading, unauthenticated и unexpected-error
states. Финансовых экранов на этом этапе нет.

## Prerequisites

- [`ADR-0001`](../../architecture/decisions/0001-react-spa-runtime-and-tooling.md)
- [`ADR-0002`](../../architecture/decisions/0002-versioned-json-api-boundary.md)
- [`ADR-0004`](../../architecture/decisions/0004-typescript-react-learning-contract.md)
- Stage 00 completed.

## Scope

### Frontend runtime

- scaffold top-level `frontend/` with React Router Framework Mode and SPA mode;
- npm + committed `package-lock.json`;
- TypeScript strict, formatter, lint, unit test, type-check and build scripts;
- `/app` root route, error boundary and minimal authenticated shell;
- same-origin development proxy;
- `frontend/README.md` with exact local commands.

### FastAPI API foundation

- `src/app/api/router.py` and versioned `src/app/api/v1/` composition;
- common JSON error envelope;
- API-specific auth/workspace dependency returning `401/403`, not `303`;
- API-specific `X-CSRF-Token` verification;
- `/api/v1/session` response with user, workspace, capabilities and CSRF token;
- API router included without changing existing SSR contracts.

### Contracts and deployment

- deterministic OpenAPI TypeScript generation command;
- generated files clearly separated from handwritten frontend models;
- Docker multi-stage frontend build and `/app/*` SPA fallback;
- legacy routes and `/api/v1/*` never swallowed by SPA fallback.

## Ordered Slices

1. Scaffold and run an empty typed React route.
2. Establish frontend quality commands before feature code.
3. Add API router, JSON error mapping and read-only session endpoint.
4. Add API CSRF dependency and focused backend tests.
5. Generate TypeScript contract and map it into a small session model.
6. Render shell states and session context.
7. Add production build/static fallback and smoke test.
8. Document the complete request -> type -> state -> render flow.

## Learning Outcomes

После этапа владелец проекта должен понимать:

- npm script и Python/uv command — похожая роль, разный ecosystem;
- `.tsx` module, function component и props;
- compile-time TypeScript type против runtime Pydantic validation;
- React render как функция от props/state;
- route module и FastAPI router — оба adapters, но работают на разных сторонах;
- cookie session, CSRF header и почему token доступен JS, а session cookie нет;
- generated DTO и handwritten feature model.

Обновить `frontend/docs/typescript-for-python.md` только этими реально
использованными concepts.

## Checks

Backend:

- API session authenticated/unauthenticated tests;
- workspace membership and disabled-member tests;
- CSRF accept/reject tests;
- JSON error status/envelope tests;
- existing auth/SSR regression tests.

Frontend:

- format, lint, TypeScript check, unit tests, production build;
- shell loading/success/401/error component tests;
- browser smoke `/app` on desktop and mobile;
- direct navigation and refresh on nested `/app/*` route;
- no console errors or failed unexpected requests.

## Out Of Scope

- manual ledger data;
- shared financial row components;
- theme switcher;
- global state/cache library;
- redesign of login/signup;
- deletion of SSR/Frontend Next code.

## Exit Gate

- clean checkout can install and build frontend deterministically;
- `/api/v1/session` obeys JSON auth/workspace/CSRF contracts;
- React shell works through same-origin development and production-shaped build;
- OpenAPI types are generated, not handwritten duplicates;
- current SSR continues to work;
- README and TypeScript-for-Python guide explain the implemented flow.

Next: [`Stage 02`](STAGE_02_VISUAL_FOUNDATION.md).

## Completion Record

Completed: 2026-07-20.

Implemented:

- React Router SPA under `/app`, strict TypeScript and complete npm quality gate;
- versioned JSON API, session/workspace/capabilities contract, API auth, CSRF and
  common error envelope;
- deterministic OpenAPI export and generated TypeScript contract with runtime
  Zod validation;
- explicit loading/authenticated/unauthenticated/error shell states;
- FastAPI SPA/static adapter, development proxy and multi-stage Docker build.

Checks run:

- Ruff, ty and 38 focused backend/API/SSR tests;
- Prettier, ESLint, TypeScript, 4 Vitest component tests and production build;
- clean `npm ci` in Docker multi-stage build;
- Chromium desktop/mobile same-origin smoke with real FastAPI, compiled assets
  and expected unauthenticated API response.

Intentional deviations:

- immutable compiled files use `/assets/*`, while client routes remain under
  `/app/*`; this matches React Router SPA output and remains isolated from
  legacy `/static` and Frontend Next `/_next/static`;
- authenticated API serialization and authenticated shell rendering are tested
  independently; real-browser smoke uses the unauthenticated state and does not
  seed a financial database.

Cleanup performed:

- frontend build/cache directories are excluded from Git and Docker context;
- no SSR route or stylesheet was removed at this foundation stage.

Learning notes updated:

- `frontend/README.md` documents the request-to-render flow and commands;
- `frontend/docs/typescript-for-python.md` explains modules, runtime validation,
  discriminated unions, components, state and effects through Python analogies.
