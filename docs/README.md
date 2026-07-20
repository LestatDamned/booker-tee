# Booker Tee Docs

This directory keeps long-lived product, domain, architecture, design, guide, and integration documents out of the repository root.

Root files are intentionally limited to:

- [`README.md`](../README.md) — project overview and local setup.
- [`AGENTS.md`](../AGENTS.md) — instructions for Codex and other coding agents.

## Reading Order

Do not read every document for every task. Start from the smallest relevant set.

For any coding task:

1. [`AGENTS.md`](../AGENTS.md)
2. This file
3. One or two task-specific documents from the table below
4. Relevant code

Для работ по новому frontend и миграции с SSR:

1. [`REACT_FRONTEND_DESIGN.md`](design/REACT_FRONTEND_DESIGN.md)
2. [`DESIGN.md`](design/DESIGN.md)
3. [`ARCHITECTURE.md`](architecture/ARCHITECTURE.md), especially application,
   domain, repository, API adapter and feature boundary rules
4. [`WORKBENCH_ROW_DESIGN.md`](design/WORKBENCH_ROW_DESIGN.md) только как
   подробный источник UX-контрактов повторяющихся строк сущностей

For financial/domain changes:

1. [`DOMAIN_MODEL.md`](domain/DOMAIN_MODEL.md)
2. [`ARCHITECTURE.md`](architecture/ARCHITECTURE.md)
3. Product docs only if the change affects scope or roadmap

## Document Status

| Document | Status | Read When |
| --- | --- | --- |
| [`PROJECT_VISION.md`](product/PROJECT_VISION.md) | active product compass | Product positioning, target users, major UX/domain decisions |
| [`DOMAIN_MODEL.md`](domain/DOMAIN_MODEL.md) | active source of truth | Database models, ledger behavior, imports, reports, financial correctness |
| [`ARCHITECTURE.md`](architecture/ARCHITECTURE.md) | active architecture reference | Code structure, feature boundaries, services/repositories/presentation layer |
| [`DESIGN.md`](design/DESIGN.md) | active design reference | General UI/UX rules, visual direction, financial UI patterns |
| [`REACT_FRONTEND_DESIGN.md`](design/REACT_FRONTEND_DESIGN.md) | active target frontend architecture | React/API boundary, UX contracts, migration strategy and repository cleanup manifest |
| [`FRONTEND_NEXT_DESIGN.md`](design/FRONTEND_NEXT_DESIGN.md) | superseded SSR strategy / behavior reference | Изолированный SSR frontend и найденные при его проектировании контракты |
| [`WORKBENCH_ROW_DESIGN.md`](design/WORKBENCH_ROW_DESIGN.md) | historical detailed UX specification | Повторяющиеся строки сущностей; переносимые interaction-контракты для React |
| [`MANUAL_LEDGER_BASELINE.md`](design/MANUAL_LEDGER_BASELINE.md) | historical migration baseline | Наблюдаемый контракт `/ledger/manual` до React migration |
| [`REFACTOR_PROJECT_DESIGN.md`](design/REFACTOR_PROJECT_DESIGN.md) | earlier refactor reference | Existing import-review behavior and presentation discoveries |
| [`MVP.md`](product/MVP.md) | historical baseline / guardrails | Preventing regressions in the completed parser-first MVP |
| [`ROADMAP.md`](product/ROADMAP.md) | planning reference | Future sequencing, not a current task list |
| [`FUTURE_IDEAS.md`](product/FUTURE_IDEAS.md) | parked ideas | Only when discussing post-core features |
| [`USER_GUIDE.md`](guides/USER_GUIDE.md) | guide/reference | User-facing wording and onboarding/help flows |
| [`ALPHA_TESTING.md`](guides/ALPHA_TESTING.md) | guide/reference | Manual alpha testing |
| [`CHAT_INTEGRATIONS.md`](integrations/CHAT_INTEGRATIONS.md) | future/partial integration plan | Chat/Telegram work only |
| [`UNKNOWN_STATEMENT_IMPORTER.md`](integrations/UNKNOWN_STATEMENT_IMPORTER.md) | active reference | Unknown bank statement mapping/import work |

## Product

- [`PROJECT_VISION.md`](product/PROJECT_VISION.md) — product compass.
- [`MVP.md`](product/MVP.md) — historical parser-first MVP baseline and guardrails.
- [`ROADMAP.md`](product/ROADMAP.md) — preferred evolution order.
- [`FUTURE_IDEAS.md`](product/FUTURE_IDEAS.md) — parked post-MVP ideas.

## Domain

- [`DOMAIN_MODEL.md`](domain/DOMAIN_MODEL.md) — financial entities and invariants.

## Architecture

- [`ARCHITECTURE.md`](architecture/ARCHITECTURE.md) — code structure, progressive
  feature architecture, feature boundaries, and data flow.

## Design

- [`DESIGN.md`](design/DESIGN.md) — UI/UX principles and visual direction.
- [`REACT_FRONTEND_DESIGN.md`](design/REACT_FRONTEND_DESIGN.md) — активная
  целевая React/API архитектура, стратегия миграции и cleanup manifest.
- [`FRONTEND_NEXT_DESIGN.md`](design/FRONTEND_NEXT_DESIGN.md) — superseded
  стратегия параллельного SSR frontend; сохраняется как behavior reference.
- [`WORKBENCH_ROW_DESIGN.md`](design/WORKBENCH_ROW_DESIGN.md) — историческая
  подробная спецификация поведения повторяющихся строк сущностей.
- [`REFACTOR_PROJECT_DESIGN.md`](design/REFACTOR_PROJECT_DESIGN.md) — справочный
  документ предыдущего import-review рефакторинга и найденного поведения.

## Guides

- [`USER_GUIDE.md`](guides/USER_GUIDE.md) — in-product guidance plan.
- [`ALPHA_TESTING.md`](guides/ALPHA_TESTING.md) — alpha tester flow and feedback checklist.

## Integrations

- [`CHAT_INTEGRATIONS.md`](integrations/CHAT_INTEGRATIONS.md) — chat integration plan.
- [`UNKNOWN_STATEMENT_IMPORTER.md`](integrations/UNKNOWN_STATEMENT_IMPORTER.md) — unknown statement import plan.
