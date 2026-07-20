# Stage 00: Decisions And SSR Freeze

Status: completed 2026-07-20.

## Goal

Устранить конфликт source of truth до появления третьего browser frontend.

## Completed Outcome

- React утвержден как target authenticated frontend.
- FastAPI остается backend и владельцем financial truth.
- `src/app/web/` Frontend Next заморожен.
- Legacy SSR сохраняется только до vertical replacement.
- Active docs направляют работу в React/API architecture.
- Приняты ADR для runtime, API, CSS/themes и learning contract.
- Manual ledger выбран первым pilot; import review — вторым complexity
  checkpoint.

## Artifacts

- [`REACT_FRONTEND_DESIGN.md`](../../design/REACT_FRONTEND_DESIGN.md)
- [`Architecture Decision Records`](../../architecture/decisions/README.md)
- [`DESIGN.md`](../../design/DESIGN.md)
- [`ARCHITECTURE.md`](../../architecture/ARCHITECTURE.md)
- [`ROADMAP.md`](../../product/ROADMAP.md)

## Exit Gate

- React не запрещен активными instructions.
- Frontend Next нигде не назван активной target strategy.
- Package/runtime/API/CSS/learning decisions имеют один accepted source.
- Никакой working SSR code не удален до replacement.

## Completion Record

```text
Completed: 2026-07-20
Implemented: active docs sync, SSR freeze markers, ADR-0001..0004
Checks run: Markdown relative links, contradiction scan, git diff --check
Intentional deviations: none
Cleanup performed: documentation source-of-truth cleanup only
Learning notes updated: React design learning contract
```
