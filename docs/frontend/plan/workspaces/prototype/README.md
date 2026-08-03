# Workspaces Slice 1 visual prototype

Статус: standalone visual prototype for product review; not a React route and
not a runtime consumer.

## Open locally

Open [`index.html`](index.html) directly in a browser. Query parameters select
the state and theme:

```text
?state=default&theme=mocha
?state=create&theme=mocha
?state=loading&theme=mocha
?state=empty&theme=mocha
?state=pending&theme=mocha
?state=conflict&theme=mocha
?state=default&theme=latte
?state=create&theme=latte
```

The default state includes current, selectable, long-name and inactive records.
Links only move between prototype states; they do not call an API or modify
application/session data.

## Design sources

The prototype imports the actual `frontend/app/styles/app.css`, including
Booker Tee tokens and Catppuccin Mocha/Latte semantic themes. Its AppShell,
workbench, button, form and panel geometry follow the current components in
`frontend/app/ui/` and `frontend/app/styles/shell.module.css`; prototype-only
CSS is isolated in [`prototype.css`](prototype.css).

It implements the accepted contract in
[`../SLICE_01_DESIGN_SPEC.md`](../SLICE_01_DESIGN_SPEC.md). It does not add a
palette, font, shared component, route, API schema or generic CRUD abstraction.

## Capture and checks

Run:

```bash
uv run python docs/frontend/plan/workspaces/prototype/capture.py \
  --output /tmp/booker-workspaces-slice01-prototype
```

The 2026-08-03 review captured 24 combinations:

- Mocha: six states at 1440×1000, 920×900 and 390×844;
- Latte: default and create at the same three viewports;
- `0` horizontal-overflow failures;
- `0` visible interactive targets below the 44 px product gate;
- `0` console errors and `0` page errors;
- create state initial focus: `#workspace-name` at all viewports;
- reduced-motion media mode enabled during capture.

Screenshots and `report.json` are generated in
`/tmp/booker-workspaces-slice01-prototype` and are intentionally not committed
as product assets.

## Prototype limitations

- It is static HTML, CSS and a small state selector, not production React.
- API authority, CSRF, idempotency, commit, hard navigation and stale recovery
  are represented visually only.
- The panel makes the background inert and places initial focus, but full focus
  return, dirty-close confirmation and screen-reader browser matrices remain
  implementation/test gates.
- AppShell navigation is illustrative and intentionally does not navigate.
- The mobile menu button is visual only; the production AppShell remains the
  source of its interaction contract.
