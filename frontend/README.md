# Booker Tee frontend

The browser application is a React Router SPA. FastAPI remains the only backend
and session owner.

```bash
cd frontend
npm ci
npm run dev
npm run check
```

Code boundaries:

- `app/routes/` — route adapters and URL state;
- `app/features/` — feature state and UI;
- `app/ui/` — proven shared components;
- `app/styles/` — semantic tokens, themes and foundation;
- `app/api/` — transport and generated API types.

React does not calculate financial status, authorization, transfer policy or
confirmation readiness. Use API DTOs and server-provided capabilities. Prefer
native controls, existing shared components and CSS Modules; do not introduce a
second styling system.

See [`docs/design/REACT_FRONTEND_DESIGN.md`](../docs/design/REACT_FRONTEND_DESIGN.md)
and [`docs/design/UI_FOUNDATION.md`](../docs/design/UI_FOUNDATION.md).
