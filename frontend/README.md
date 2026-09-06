# Booker Tee frontend

The browser application is a React Router SPA. FastAPI remains the only backend
and session owner.

```bash
cd frontend
npm ci
npm run dev
npm run check
```

Vitest runs `app/**/*.test.ts` in Node and `app/**/*.test.tsx` in jsdom
with React cleanup. Keep pure function and API tests in `.test.ts`; use
`.test.tsx` for component tests. A `.test.ts` file needing browser globals can
opt into jsdom with `// @vitest-environment jsdom`; React rendering belongs in
the DOM project. File isolation stays enabled in both projects.

Run one group with `npm test -- --project=node` or `npm test -- --project=dom`.
CI runs each command from `npm run check` as a separate step so its duration
and failures are visible.

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
