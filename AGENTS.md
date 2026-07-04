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
maintainability, SSR/UI consistency, and user workflows.

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
- Jinja2 for SSR
- HTMX for server-driven interactivity
- Alpine.js for small local UI state
- Tailwind/project CSS
- pdfplumber and file extractors for statement import
- uv
- Ruff
- ty
- pytest

Do not introduce a new frontend framework, background queue, AI stack, storage
backend, or large infrastructure dependency without a strong reason and user
approval.

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
- UI/SSR/templates/CSS/actions:
  [`docs/design/DESIGN.md`](docs/design/DESIGN.md).
- Current import review refactor:
  [`docs/design/REFACTOR_PROJECT_DESIGN.md`](docs/design/REFACTOR_PROJECT_DESIGN.md).
- Historical parser-first MVP guardrails:
  [`docs/product/MVP.md`](docs/product/MVP.md).

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

- Routers handle HTTP, dependencies, forms, redirects, template responses, and
  HTMX responses.
- Application/use-case code owns workflows, orchestration, and transactions.
- Domain code owns pure policies, calculations, validators, and status
  resolvers.
- Presenters/ViewModels prepare UI data for Jinja and must not mutate financial
  data.
- Repositories contain database queries only.
- Models define persistence only.
- Infrastructure adapters handle files, extraction, external services, and
  provider clients.
- Templates render prepared data and must not contain business rules.

Default flow:

```text
Router -> Service / Application Use Case -> Repository -> Model
Router -> Service / Use Case -> Presenter / ViewModel -> Jinja partial
```

Keep files readable. If one file starts telling several stories, split by reason
to change: `routes/`, `application/`, `domain/`, `presentation/`, `mapping/`, or
`infrastructure/`.

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

## 11. SSR/UI Rules

Use server-side rendering with Jinja2 and HTMX.

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

Templates should render prepared data. They should not compute financial state,
review state, duplicate policy, transfer direction, action policy, or
confirmation readiness.

For complex screens use:

```text
Router -> Service / Use Case -> Presenter / ViewModel -> Jinja partial
```

For the current import review refactor, follow
[`docs/design/REFACTOR_PROJECT_DESIGN.md`](docs/design/REFACTOR_PROJECT_DESIGN.md).

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
- ViewModel/action policy behavior for complex SSR screens.

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

- new frontend framework or SPA rewrite;
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
