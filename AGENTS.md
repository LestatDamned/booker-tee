# AGENTS.md - Booker Tee

Project instructions for Codex and other coding agents.

Official references:

- Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- uv: https://docs.astral.sh/uv/
- Ruff: https://docs.astral.sh/ruff/
- ty: https://docs.astral.sh/ty/

---

## 1. Product Focus

Booker Tee is a private financial assistant focused on reliable financial data
import, review, and ledger correctness.

The original parser-first MVP has been completed and exceeded. The current
product challenge is to keep the financial core trustworthy while improving
maintainability, migrating the authenticated frontend, and clarifying user
workflows.

Core flow:

```text
PDF/XLSX/manual entry
  -> raw extracted data
  -> normalized draft rows
  -> validation and deduplication
  -> user review
  -> confirmed Operation + MoneyEntry
  -> balances and reports
```

Do not turn Booker Tee into a broad AI, asset-management, CRM, ERP, or SaaS
billing platform unless explicitly requested.

---

## 2. Non-Negotiable Principles

1. Reliability over magic.
2. Financial correctness over decorative polish.
3. User review over silent automation.
4. Raw imported data must never be lost.
5. Internal transfers must never be counted as income, expense, profit, or
   property ROI.
6. Workspaces are strict data boundaries.
7. Private financial data must not be sent to external AI/API services unless
   explicitly requested.
8. Parsers must not create confirmed ledger records directly.
9. Duplicate imports must not double-count money.
10. Confirmed financial records should be corrected carefully, not casually
    hard-deleted.

---

## 3. Tech Stack

Use the repository's current stack unless a task explicitly changes it:

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0 async style
- Alembic
- Pydantic v2
- PostgreSQL
- TypeScript in strict mode
- React with React Router Framework Mode in SPA mode
- semantic CSS tokens, theme files, and component CSS Modules
- versioned FastAPI JSON API for the React application
- Jinja2, HTMX, Alpine.js, and project CSS only for legacy SSR during migration
- pdfplumber and file extractors for statement import
- uv
- Ruff
- ty
- pytest

React is an approved target frontend. Do not introduce another frontend
framework, Node backend, background queue, AI stack, storage backend, or large
infrastructure dependency without a strong reason and user approval.

---

## 4. Package Management And Checks

Use Astral tooling.

Package management:

```bash
uv sync
uv add <package>
uv add --dev <package>
uv run <command>
```

Frontend package management after `frontend/` is scaffolded:

```bash
npm install
npm ci
npm run <script>
```

Use one committed `package-lock.json`. Do not mix npm, pnpm, and yarn.

Do not use plain `pip install`, Poetry, Pipenv, or ad-hoc virtualenv commands
unless explicitly requested.

Quality commands:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

Before finishing a coding task, run the relevant checks. If dependencies,
database, browser tooling, or infrastructure prevent a check from running, say
that clearly in the final response.

---

## 5. Documentation Reading Order

Do not read every document for every task. Start with:

1. This `AGENTS.md`.
2. [`docs/README.md`](docs/README.md).
3. One or two task-specific documents.
4. Relevant code.

Task-specific documents:

- Product/scope decisions:
  [`docs/product/PROJECT_VISION.md`](docs/product/PROJECT_VISION.md) and
  [`docs/product/ROADMAP.md`](docs/product/ROADMAP.md).
- Financial/domain/model/report changes:
  [`docs/domain/DOMAIN_MODEL.md`](docs/domain/DOMAIN_MODEL.md).
- Code structure/layers/module boundaries:
  [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md).
- UI/UX/React/API/CSS/actions:
  [`docs/design/DESIGN.md`](docs/design/DESIGN.md).
- Reusable React UI, component selection and CSS ownership:
  [`docs/design/UI_FOUNDATION.md`](docs/design/UI_FOUNDATION.md).
- Active React frontend architecture and migration strategy:
  [`docs/design/REACT_FRONTEND_DESIGN.md`](docs/design/REACT_FRONTEND_DESIGN.md).
- React implementation sequence; read the index and current stage only:
  [`docs/frontend/plan/README.md`](docs/frontend/plan/README.md).
- Accepted React migration decisions:
  [`docs/architecture/decisions/README.md`](docs/architecture/decisions/README.md).

Respect existing decisions unless the task asks to change them.

---

## 6. Architecture Rules

Use progressive feature architecture.

Simple features may stay simple:

```text
feature/
  models.py
  repository.py
  service.py
  router.py
```

Complex features may grow internal layers:

```text
feature/
  routes/
  application/
  domain/
  presentation/
  mapping/
  infrastructure/
```

Layer responsibilities:

- Routers are presentation adapters. JSON API routers handle HTTP schemas,
  dependencies and responses; legacy SSR routers may handle forms, redirects,
  templates and HTMX responses until their workflow is migrated.
- Application/use-case code owns workflows, orchestration, and transactions.
- Domain code owns pure policies, calculations, validators, and status
  resolvers.
- Legacy presenters/ViewModels prepare UI data for Jinja and must not mutate
  financial data. React builds feature view state from versioned API DTOs.
- Repositories contain database queries only.
- Models define persistence only.
- Infrastructure adapters handle files, extraction, external services, and
  provider clients.
- Templates and React components render prepared data and must not contain
  financial or authorization rules.

Default flow:

```text
Router -> Service / Application Use Case -> Repository -> Model
React -> API Router -> Service / Application Use Case -> Repository -> Model
Legacy SSR Router -> Service / Use Case -> Presenter / ViewModel -> Jinja
```

Keep files readable. If one file starts telling several stories, split by reason
to change: `routes/`, `application/`, `domain/`, `presentation/`, `mapping/`, or
`infrastructure/`.

The target React application lives in top-level `frontend/`; its versioned JSON
API adapter lives in `src/app/api/`. Feature-specific domain and application
code remains in `src/app/features/`. `src/app/web/` has no active source or
runtime consumer; do not repopulate it.
Follow [`docs/design/REACT_FRONTEND_DESIGN.md`](docs/design/REACT_FRONTEND_DESIGN.md)
for boundaries, learning rules, migration and delete gates.

---

## 7. Code Readability Rules

Prefer explicit imports and visible dependencies.

Good:

```python
from app.features.ledger.application.manual_operations import ManualOperationService
```

Avoid:

```python
from app.features.ledger.application import *
```

Avoid dynamic import magic and implicit registration through import side effects
unless documented and genuinely needed.

Prefer actor-oriented workflow APIs:

```text
ManualOperationService.create_expense(...)
LedgerPostingService.post_transfer(...)
ImportReviewPresenter.build_item(...)
TransactionRuleMatcher.match(...)
DuplicateDetector.mark_duplicate_candidates(...)
```

Free functions are fine for small pure helpers, predicates, formatting,
normalization, and simple calculations. Business actions, workflows, external
operations, and state transitions should usually live on a named service,
policy, presenter, matcher, resolver, factory, or adapter.

Reuse existing policies, presenters, formatters, option builders, parsers, and
partials when they express the same concept. Avoid duplication for money
formatting, review state, action policy, transfer preview, workspace checks,
dedupe, and status transitions.

Do not create generic abstractions before repeated stable use exists.

Code should tell a clear story through domain-specific actors and actions. Use
names such as `ManualLedgerPresenter.present(...)` and
`ManualLedgerResponses.replace_row(...)` instead of vague names such as
`process_data(...)`, `handle(...)`, `Manager`, `Processor`, `helpers.py`, or
`utils.py`. A generic name is acceptable only when its meaning is genuinely
unambiguous in the local context.

Keep handwritten Python modules at a readable middle size. A module approaching
roughly 250-350 lines should trigger a cohesion review; handwritten modules
should not quietly grow beyond 500 lines. These are review signals, not targets
or mechanical limits. Split a module only when it tells multiple stories or has
multiple reasons to change. Do not replace one coherent module with many tiny
files that force readers to jump between them.

Prefer named actor APIs for business workflows and related presentation
behavior, without wrapping every helper in a class. Free functions remain the
right choice for small pure predicates, focused formatting or normalization,
framework callbacks, and simple calculations without an owning role.

Reuse code when the same stable concept and contract recur. Similar-looking
code is not sufficient reason for a shared abstraction. Keep a feature-specific
implementation local until a reusable responsibility has become clear.

Keep imports explicit and import objects from the module that defines them.
Avoid wildcard imports, broad package re-exports, dynamic import magic, and
`__init__.py` facades that hide architectural ownership.

---

## 8. Workspace-First Rule

A `Workspace` is the main ownership boundary for financial data.

Every query for workspace-owned data must filter by `workspace_id` or a strictly
validated workspace-owned parent.

Bad:

```python
select(Operation).where(Operation.id == operation_id)
```

Good:

```python
select(Operation).where(
    Operation.id == operation_id,
    Operation.workspace_id == current_workspace_id,
)
```

Never trust `workspace_id` from a form without checking membership. Chat and
integration actions must obey the same workspace rules as web routes.

---

## 9. Financial Domain Rules

Use this accounting shape:

```text
Operation 1 -> N MoneyEntry
```

Concepts:

```text
Account         = where money is stored
Operation       = business meaning of a money event
MoneyEntry      = signed movement on one account
Category        = why money appeared/disappeared
Property        = optional property/object link
RawTransaction  = imported row before confirmation
```

Rules:

- Income/expense changes financial result.
- Transfer changes only the location of money.
- Transfer operations must have `affects_profit=false`.
- Draft/review/ignored/duplicate operations do not affect official balances.
- Balances are derived from confirmed `MoneyEntry` records.
- Use `Decimal` in Python and `Numeric` in PostgreSQL.
- Never use `float` for money.
- Store currency explicitly.
- Tenant security deposits are not income until retained.

---

## 10. Import And Review Rules

Import must be robust and reviewable:

```text
uploaded_documents
  -> parse_attempts
  -> raw_transactions
  -> validation / deduplication / suggestions
  -> review
  -> confirmed operations + money entries
```

Rules:

1. Store document metadata and file reference before parsing.
2. Preserve extracted raw text/tables/payloads where available.
3. Save every parser run as a `ParseAttempt`.
4. Save extracted rows as `RawTransaction`.
5. Parser code never creates confirmed operations directly.
6. Failed parsing preserves document and safe error details.
7. Uncertain validation requires review.
8. Dedupe/idempotency prevents repeated imports from double-counting money.
9. Transaction rules may suggest/prefill, but must not bypass financial
   invariants.
10. `ready_to_confirm` is a presentation state, not a backend status.

---

## 11. Frontend/UI Rules

React is the target authenticated frontend. Existing Jinja2/HTMX pages remain
operational only until their vertical React replacement passes cutover gates.

Current visual direction:

```text
modern financial workbench
dark-first
calm
dense
precise
trustworthy
with restrained rebellious creativity
```

React components and legacy templates should render prepared data. They must not
compute financial state, permission, duplicate policy, transfer direction or
confirmation readiness.

Target flow for complex screens:

```text
React feature -> versioned API -> Service / Use Case -> Repository
```

Follow [`docs/design/REACT_FRONTEND_DESIGN.md`](docs/design/REACT_FRONTEND_DESIGN.md)
and [`docs/design/DESIGN.md`](docs/design/DESIGN.md). Before creating a React
page or shared component, use
[`docs/design/UI_FOUNDATION.md`](docs/design/UI_FOUNDATION.md) to select an
existing component and CSS composition. For migrated workflows, the React
feature code, API schemas, application policies, and tests are the behavior
reference; do not restore deleted SSR migration specifications.

---

## 12. Security And Privacy

This project handles sensitive financial data.

- Never commit real bank statements, passports, contracts, `.env` files, tokens,
  passwords, or secrets.
- Use sanitized fixtures for tests.
- Do not log full PDF text, full extracted tables, full card numbers, account
  numbers, tokens, passwords, or secrets.
- Mask sensitive values in logs and errors.
- Prefer local processing for financial documents.
- External AI/API processing requires explicit user/product decision.
- Add authorization checks before data access.

---

## 13. Testing Expectations

Prioritize tests for:

- internal transfer does not affect profit;
- income/expense affects profit correctly;
- workspace isolation;
- parser/raw row preservation;
- failed parser attempts preserve uploaded documents;
- control-total mismatch creates review state;
- dedupe detects repeated imports;
- category/rule behavior stays workspace-scoped;
- API schema/auth/error contracts and React state behavior for migrated screens;
- ViewModel/action policy behavior only for legacy screens that still have a
  runtime consumer.

---

## 14. Database And Migrations

- Use Alembic for every schema change.
- Keep migrations deterministic.
- Avoid destructive migrations unless explicitly requested.
- Use indexes for common workspace-scoped queries.
- Add foreign keys for ownership and integrity.
- Prefer explicit enum values and stable names.

---

## 15. Avoid Unless Requested

Do not introduce these unless explicitly requested and scoped:

- another frontend framework, Node backend, microfrontend architecture, or
  second permanent authenticated UI;
- external AI/RAG/Text-to-SQL;
- external document processing services;
- full property CRM;
- tenant/lease/meter/vacancy workflows;
- complex RBAC redesign;
- SaaS billing;
- broad product expansion unrelated to import/review/ledger clarity.

Chat integrations already exist. Treat them as integration features with strict
workspace boundaries; do not expand them into a second app or parallel ledger.

---

## 16. Final Response Format For Coding Tasks

When finishing a coding task, report:

1. What changed.
2. Files changed.
3. Commands run.
4. Test/lint/type-check result.
5. Known limitations or follow-up needed.

Do not claim checks passed if they were not run.
