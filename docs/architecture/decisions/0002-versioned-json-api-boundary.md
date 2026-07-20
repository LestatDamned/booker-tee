# ADR-0002: Versioned JSON API Boundary

Status: accepted 2026-07-20.

## Context

Legacy browser routes смешивают forms, redirects, presenters и HTML responses.
Их нельзя безопасно использовать как React API. Финансовые и workspace rules
должны остаться в существующих application/domain layers.

## Decision

- React API живет в `src/app/api/v1/`.
- API router вызывает application use case/query, а не legacy HTTP route.
- API использует отдельные Pydantic request/response schemas.
- Session остается в `HttpOnly`, `SameSite=Lax`, production-secure cookie.
- `/api/v1/session` возвращает user/workspace context, capabilities и CSRF token.
- Unsafe requests передают CSRF через `X-CSRF-Token`.
- API возвращает JSON `401`, `403`, `404`, `409`, `422` и безопасный `5xx`, а не
  login redirect или HTML fragment.
- Money передается decimal string вместе с currency и server-owned semantics.
- API возвращает capabilities, но React владеет labels и action placement.
- TypeScript DTO/client генерируются из FastAPI OpenAPI детерминированным quality
  command и не редактируются вручную.

## Consequences

- SSR auth/workspace dependencies сохраняются отдельно до удаления legacy routes.
- Backend contract tests становятся обязательными до component work.
- Breaking API change требует обновления OpenAPI artifact и frontend tests.
- Generated DTO отображается в focused feature model на frontend boundary и не
  распространяется бездумно через component tree.
