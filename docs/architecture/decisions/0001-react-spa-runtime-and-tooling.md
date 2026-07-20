# ADR-0001: React SPA Runtime And Tooling

Status: accepted 2026-07-20.

## Context

Authenticated workflows уже требуют сложного client state. FastAPI остается
полноценным backend, текущий deployment — один Python container без Node runtime,
а владелец проекта впервые системно изучает TypeScript и React.

## Decision

- Новый frontend находится в top-level `frontend/`.
- Используются TypeScript strict, React и React Router Framework Mode.
- Начальный rendering mode — SPA с `ssr: false`; Node не становится backend.
- Package manager — npm с одним committed `package-lock.json`.
- Clean install выполняется через `npm ci`; scripts — через `npm run`.
- Development server проксирует `/api` и auth routes в FastAPI.
- Production build выполняется в отдельной Node stage Docker build.
- Собранные immutable assets и SPA fallback `/app/*` отдаются same-origin с
  FastAPI `/api/v1/*`.
- Минимальный runtime — Node 22.22; точные dependency versions фиксируются
  scaffold-generated lockfile.

## Why

- React Router дает route modules и code splitting без второго business backend.
- SPA подходит приватным financial routes без SEO requirement.
- npm имеет наименьший дополнительный learning/tooling burden и поставляется
  вместе с Node.
- Same-origin сохраняет текущую cookie model и не требует permissive CORS.
- Multi-stage build сохраняет один production runtime container.

## Consequences

- Dockerfile нужно будет расширить Node build stage.
- Local host development требует поддерживаемый Node release.
- FastAPI/static adapter должен корректно отличать `/api`, assets и SPA fallback.
- Переход к reverse proxy/CDN возможен позже без изменения API или React code.

## References

- [React: Creating a React App](https://react.dev/learn/creating-a-react-app)
- [React Router modes](https://reactrouter.com/start/modes)
- [React Router SPA](https://reactrouter.com/how-to/spa)
