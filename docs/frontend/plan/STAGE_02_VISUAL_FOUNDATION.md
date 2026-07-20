# Stage 02: Visual Foundation

Status: next.

## Goal

Создать маленькую theme-ready component foundation, которая сохраняет геометрию
Booker Tee и не переносит legacy/Frontend Next stylesheets.

## User-Visible Outcome

В test/gallery surface видны базовые controls, money states и workbench geometry
в Catppuccin Mocha и минимальной test theme на desktop, `920px` и mobile.

## Prerequisites

- Stage 01 completed.
- [`ADR-0003`](../../architecture/decisions/0003-tokenized-css-and-themes.md)
- current/Next manual-ledger screenshots доступны как comparison source.

## Scope

- semantic color, typography, spacing, radius, shadow, motion and control tokens;
- Catppuccin Mocha theme values;
- intentionally plain test theme proving token completeness;
- reset/global foundation without feature styles;
- component CSS Modules;
- `Button`, `IconButton`, `Field`, `FormError`, `MoneyValue`, `Badge`,
  `RequestState`, `PageHeader`;
- first geometry primitives for `ActionStack`, `WorkbenchRow` and
  `ExpansionPanel`;
- visual fixtures for normal, hover, focus, disabled, loading and error states;
- screenshot comparison with current SSR and Frontend Next geometry.

## Extraction Method

For each useful current/Next CSS decision:

```text
observe behavior and geometry
-> identify reusable semantic responsibility
-> name token or component ownership
-> implement from scratch in React CSS layer
-> compare screenshots and interaction states
-> do not copy legacy selector
```

## Ordered Slices

1. Record page/row/control geometry baseline.
2. Define token layers and Catppuccin semantic mapping.
3. Add test theme before component count grows.
4. Implement typography, focus and request-state primitives.
5. Implement buttons, fields and money/status semantics.
6. Implement row/action/expansion geometry through composition slots.
7. Run responsive, keyboard, contrast and no-overflow audit.
8. Delete the standalone `/_next/foundation` showcase/route only after
   replacement evidence and a consumer search; keep Next shared files still used
   by its manual runtime until Stage 05.

## Learning Outcomes

- CSS custom property как runtime value, TypeScript type как compile-time rule;
- semantic token против raw palette value;
- CSS Module и локальная область selector;
- React `children`/composition как аналог передачи behavior/content, но не
  Python inheritance;
- props contract и зачем избегать десятков boolean flags;
- native HTML semantics и `:focus-visible`.

## Checks

- every semantic color token resolved in both themes;
- no raw palette values in component/feature CSS;
- keyboard and visible focus;
- accessible names and disabled/loading semantics;
- desktop/920/mobile screenshots;
- no unintended horizontal overflow or layout jump;
- geometry differences from baseline documented as intentional;
- component tests and production build pass.

## Out Of Scope

- product theme switcher/preferences;
- manual ledger API;
- universal form generator;
- chart library;
- copying `app.css` or `src/app/web/static` into React.

## Exit Gate

- two themes render the same component geometry;
- shared components cover only stable responsibilities;
- manual ledger can be built without introducing a second CSS foundation;
- standalone Frontend Next foundation showcase has no unique remaining contract;
  its removal does not break the still-running Next manual workflow.

Next: [`Stage 03`](STAGE_03_MANUAL_LEDGER_READ.md).
