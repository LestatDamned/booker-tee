# ARCHITECTURE.md - Booker Tee

Engineering architecture for Booker Tee.

Status: active architecture reference.

Read when changing code structure, layers, routers, services, repositories,
templates, presentation/ViewModel code, import workflows, ledger posting,
workspace access, or integration boundaries.

Do not use as a product roadmap or historical MVP build plan. For product scope
read [`PROJECT_VISION.md`](../product/PROJECT_VISION.md) and
[`ROADMAP.md`](../product/ROADMAP.md). For domain invariants read
[`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md). For UI/SSR refactoring read
[`DESIGN.md`](../design/DESIGN.md) and
[`REFACTOR_PROJECT_DESIGN.md`](../design/REFACTOR_PROJECT_DESIGN.md).

Current assessment: the original parser-first MVP is complete and exceeded.
Architecture now needs to protect clarity, maintainability, financial
correctness, and workspace safety as the project grows.

---

## 1. Architecture Goal

Booker Tee must remain a reliable financial-data import, review, and ledger
system.

Core flow:

```text
PDF bank statement / manual entry
  -> UploadedDocument
  -> ParseAttempt
  -> raw extracted data
  -> RawTransaction
  -> normalization
  -> validation and deduplication
  -> review
  -> confirmed Operation + MoneyEntry
  -> balances and reports
```

Architectural mantra:

```text
Preserve the source.
Parse safely.
Normalize carefully.
Validate before trust.
Review before posting.
Post atomically.
Never double-count money.
Always scope by workspace.
```

---

## 2. Tech Stack

Use the stack already defined in [`AGENTS.md`](../../AGENTS.md) unless a later
documented decision changes it.

```text
Python 3.12+
FastAPI
SQLAlchemy 2.0 async
Alembic
Pydantic v2
PostgreSQL
Jinja2 SSR
HTMX
Alpine.js for small local UI state
Tailwind / project CSS
pdfplumber and file extractors
uv
Ruff
ty
pytest
```

Do not introduce a new frontend framework, background queue, AI stack, or storage
backend without a concrete product need and an architecture update.

---

## 3. Current Repository Shape

Current high-level layout:

```text
src/app/
  main.py
  core/
  db/
  shared/
  features/
    accounts/
    categories/
    chat_integrations/
    dashboard/
    imports/
    ledger/
    properties/
    reports/
    transaction_rules/
    users/
    workspaces/
  templates/
  static/
tests/
docs/
migrations/
```

This is a feature-driven project. Feature boundaries matter more than a global
technical-layer folder structure.

---

## 4. Progressive Feature Architecture

Booker Tee uses progressive feature architecture:

```text
Small features stay simple.
Complex workflows grow internal layers.
Split by reason to change, not by fashion.
```

### Simple Feature

Use this for small CRUD-like modules:

```text
feature/
  models.py
  repository.py
  service.py
  router.py
```

Examples: `accounts`, `categories`, `properties` until their workflows become
more complex.

### Medium Feature

Use this when a feature has several workflows or non-trivial UI state:

```text
feature/
  models.py
  repository.py
  service.py
  router.py
  application/
  domain/
  presentation/
```

### Complex Feature

Use this for modules with multiple workflows, adapters, and SSR surfaces:

```text
feature/
  models.py
  repository.py
  query_repository.py
  service.py
  routes/
  application/
  domain/
  presentation/
  mapping/
  infrastructure/
```

Examples: `imports`, `ledger`, `chat_integrations`.

Do not create every folder by default. Add a folder when the module has a real
reason to change along that boundary.

---

## 5. Layer Responsibilities

Primary flow:

```text
Router -> Application Use Case / Service -> Repository -> Model
```

For complex SSR screens:

```text
Router -> Service / Use Case -> Presenter / ViewModel -> Jinja partial
```

Responsibilities:

| Layer | Responsibility |
| --- | --- |
| `router.py` / `routes/` | HTTP, dependencies, forms, redirects, template responses, HTMX responses. |
| `service.py` | Facade for feature operations and compatibility layer for simple workflows. |
| `application/` | Use cases, commands, workflows, orchestration, transactions. |
| `domain/` | Pure policies, calculations, status resolvers, validation rules. No HTTP, Jinja, or SQLAlchemy session. |
| `presentation/` | ViewModels, presenters, action policies, form option builders. No financial mutation. |
| `mapping/` | DTO/model/form conversion, factories, translation between layers. |
| `repository.py` | Database queries only. No business decisions. No commits unless explicitly documented. |
| `models.py` | SQLAlchemy persistence shape. No service/router/template knowledge. |
| `infrastructure/` | File storage, PDF/excel extraction, external adapters, provider clients. |
| `templates/` | Render prepared data. No business rules. |

Rules:

- Routers do not contain business scenarios.
- Repositories do not call services.
- Models do not reach into repositories, services, HTTP, or templates.
- Domain code does not know about HTTP, Jinja, HTMX, SQLAlchemy sessions, or
  request objects.
- Presentation code does not post ledger records or mutate financial data.
- Cross-feature behavior goes through service/use-case APIs, not direct random
  table manipulation.

---

## 6. File Size And Responsibility Rules

Code should read like a book with chapters, not one endless paragraph.

Soft thresholds:

```text
router.py over 250-300 lines
  -> split into routes/

service.py over 300-400 lines
  -> extract workflows into application/

many pure conditions/calculations
  -> extract domain/

many template conditionals or option builders
  -> extract presentation/

many DTO/form/model conversions
  -> extract mapping/

file storage, PDF extraction, external clients
  -> infrastructure/
```

Thresholds are not mechanical laws. They are prompts to ask: "How many stories
does this file tell?"

---

## 7. Explicit Code Style Rules

### Explicit Imports

Prefer explicit imports over hidden magic.

Good:

```python
from app.features.ledger.application.manual_operations import ManualOperationService
from app.features.imports.presentation.review import ImportReviewPresenter
```

Avoid:

```python
from app.features.ledger.application import *
```

Also avoid dynamic imports, implicit registration through import side effects,
or module-level magic unless there is a clear and documented reason.

When reading a file, it should be obvious where each dependency comes from and
which object owns the action.

### Actor-Oriented Workflows

Prefer actor-oriented APIs for business actions and workflows:

```text
ManualOperationService.create_expense(...)
LedgerPostingService.post_transfer(...)
ImportReviewPresenter.build_item(...)
TransactionRuleMatcher.match(...)
DuplicateDetector.mark_duplicate_candidates(...)
```

This reads as:

```text
who does what
```

Free functions are allowed for small pure helpers, predicates, formatting,
normalization, and simple calculations. But if a function represents a business
action, workflow, external operation, or state transition, prefer a named
service, policy, presenter, matcher, resolver, factory, or adapter with an
explicit method.

### Reuse Without Premature Abstraction

Reuse existing domain policies, presenters, option builders, parsers, formatters,
and UI partials when they express the same concept.

Do not duplicate logic for:

- money formatting;
- operation type labels;
- review states;
- action policies;
- category/property options;
- transfer preview;
- workspace checks;
- dedupe and status transitions;
- parser row normalization.

But do not create generic abstractions before there are real repeated usages and
the shared concept is stable.

Principle:

```text
Explicit dependencies.
Actor-oriented workflows.
Reusable concepts.
No hidden magic.
```

---

## 8. Current Feature Guidance

### `imports`

`imports` is a complex feature.

Expected shape:

```text
imports/
  models.py
  repository.py
  query_repository.py
  service.py
  routes/
  application/
  domain/
  infrastructure/
  mapping/
  parsing/
  presentation/
```

Guidance:

- `routes/` owns HTTP/HTMX endpoints for documents, review, and mapping.
- `application/` owns workflows: parse, reparse, review actions, mapping apply,
  known/unknown statement pipelines.
- `domain/` owns deduplication, validation, and status/policy logic.
- `infrastructure/` owns storage and file extraction adapters.
- `parsing/` owns parser interfaces, registry, parser implementations, and
  parser support utilities.
- `presentation/` owns page contexts, review item ViewModels, action policy, and
  form options.
- Parsers never create confirmed operations directly.

### `ledger`

`ledger` is a complex financial feature.

Guidance:

- `application/` owns imported posting, manual operations, transfer suggestions,
  undo, listing, and document status coordination.
- `domain/` owns money rules, raw transaction status resolving, and pure text or
  money helpers.
- `mapping/` owns DTO/factory conversion.
- `service.py` should remain a facade, not a large workflow dumping ground.
- Ledger posting must be atomic.

### `chat_integrations`

`chat_integrations` is an integration feature, not the core ledger.

Guidance:

- Providers and transport adapters live under `providers/`.
- Routing/action parsing lives under `routing/` and `actions/`.
- User-facing chat presentation lives under `presentation/`.
- Use cases live under `use_cases/`.
- Chat actions must obey workspace permissions and reuse normal application
  services for financial behavior.

### `transaction_rules`

Rules should remain suggestion/autofill logic, not silent financial posting.

Guidance:

- Matching policy belongs in `domain/`.
- Rule management belongs in `application/`.
- Templates receive prepared options and labels.
- `auto_apply` may prefill structured fields but must not bypass review and
  financial invariants.

### Simple CRUD Features

`accounts`, `categories`, `properties`, `reports`, `dashboard`, `users`, and
`workspaces` may remain simple until complexity forces a split.

When UI logic grows, add `presentation/`. When workflows grow, add
`application/`. When pure rules grow, add `domain/`.

---

## 9. SSR And Template Architecture

Use server-side rendering with Jinja2 and HTMX.

Target flow:

```text
Router -> Service / Use Case -> Presenter / ViewModel -> Jinja partial
```

Rules:

- Templates render prepared data.
- Templates do not compute financial state, action policy, duplicate policy,
  transfer direction, or confirmation readiness.
- HTMX partial responses reuse the same ViewModel builders as full-page
  rendering.
- Complex repeated UI should become partials.
- Domain-specific UI partials stay inside the feature until they prove reusable.
- Generic UI partials may live under `templates/ui/` or `templates/components/`
  when they are stable.

Current detailed import review plan lives in
[`REFACTOR_PROJECT_DESIGN.md`](../design/REFACTOR_PROJECT_DESIGN.md).

---

## 10. Import And Parser Architecture

Parser code is isolated from HTTP, templates, and ledger posting.

Conceptual parser flow:

```text
Extractor -> ExtractedStatement -> ParserRegistry -> Parser -> Parsed rows
```

Rules:

- Extractors read files and return extracted text/tables.
- Parsers convert extracted data into structured draft rows.
- Parsers preserve raw payloads.
- Parsers do not post ledger records.
- Parser failures are business states, not crashes.
- Reparse creates a new `ParseAttempt`.
- Unknown statement mapping may create draft raw rows, but still goes through
  validation and review.

If parsing fails:

```text
UploadedDocument.status = failed_to_parse or requires_review
ParseAttempt.status = failed or requires_review
safe error message is stored
original file and raw extraction are preserved when available
```

---

## 11. Ledger Posting Architecture

Confirmed accounting records are created only through ledger application/service
logic.

Rules:

1. Posting happens in one database transaction.
2. Every `Operation` belongs to a workspace.
3. Every `MoneyEntry` belongs to an operation and account.
4. Account, category, property, operation, and money entries must belong to the
   same workspace.
5. Transfers create source and destination entries.
6. Transfers always have `affects_profit=false`.
7. Raw import confirmation links `RawTransaction` to the created/linked
   `Operation`.
8. Re-confirming an already confirmed raw row must be idempotent or rejected
   safely.

Account balances are derived from confirmed `MoneyEntry` rows. Do not update
account balances by hand in random feature services.

---

## 12. Workspace Security

Workspace boundaries are mandatory.

Access flow:

```text
request user
  -> resolve current workspace
  -> verify membership
  -> authorize action
  -> execute workspace-scoped query
```

Rules:

- Never trust `workspace_id` from a form without checking membership.
- Never fetch workspace-owned data by object id alone.
- Chat/integration actions must follow the same workspace checks as web routes.
- Presenters and templates must not become authorization boundaries.

---

## 13. Transactions

Use one SQLAlchemy async session per request or task.

Preferred pattern:

```text
Router receives dependency-provided session
Service / use case performs business operation
Repository executes queries
Service / use case owns commit/rollback for writes
Repository never commits
```

Atomic operations:

```text
confirm raw row -> create Operation -> create MoneyEntry -> link RawTransaction
create transfer -> create Operation -> create source entry -> create destination entry
parse document -> create ParseAttempt -> save extraction -> create RawTransaction rows -> update statuses
```

If any part of an atomic operation fails, rollback the whole operation.

---

## 14. Status Model

Use explicit statuses instead of unclear boolean flags.

Current core statuses are documented in
[`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md). Important sets:

```text
UploadedDocumentStatus:
uploaded, pending_parse, parsing, parsed, requires_review,
failed_to_parse, imported, ignored

ParseAttemptStatus:
running, success, requires_review, failed

RawTransactionStatus:
extracted, normalized, suggested, needs_review, matched,
ignored, duplicate, possible_duplicate, failed, confirmed

OperationStatus:
draft, needs_review, confirmed, ignored, duplicate
```

Do not confuse presentation states with backend statuses. Example:
`ready_to_confirm` is currently a presentation-only state.

---

## 15. Deduplication And Validation

Duplicate imports must not double-count money.

Rules:

- Exact duplicate files should not create another active import silently.
- Exact duplicate rows should be marked duplicate or skipped safely.
- Possible duplicate rows should go to review.
- Duplicate rows must not become new ledger records unless the user explicitly
  resolves the conflict.

When bank statement totals are available, validate:

```text
opening_balance + inflow - outflow = closing_balance
sum(parsed positive rows) = total inflow
abs(sum(parsed negative rows)) = total outflow
```

If validation fails, require review. Do not automatically post confirmed
operations.

---

## 16. File Storage

The current storage backend may be local filesystem. The backend should remain
replaceable later.

Rules:

- Do not store large PDF blobs in normal relational rows.
- Store file metadata and storage key in the database.
- Generate server-side file names.
- Do not trust user-provided file names for paths.
- Enforce content type, extension, and file size policy.
- Keep original files available for reparse.

---

## 17. Background Jobs

Do not introduce Celery/Redis just because parsing exists.

Current policy:

```text
Small/medium operations may run synchronously or through FastAPI BackgroundTasks.
Heavy parsing, retries, scheduled imports, and notifications may move to Celery later.
```

Important rule:

```text
The same application service should be callable from HTTP routes and workers.
```

Do not duplicate parsing or posting logic in worker-only modules.

---

## 18. Configuration And Secrets

Use Pydantic settings.

Rules:

- No secrets in source code.
- No hardcoded absolute developer paths.
- File storage path is configurable.
- Upload limits are configurable.
- Tests use separate settings or transactional fixtures.
- External services require explicit settings and product decision.

---

## 19. Logging And Privacy

Use structured logs for import and integration workflows.

Useful fields:

```text
workspace_id
user_id
uploaded_document_id
parse_attempt_id
raw_transaction_id
operation_id
parser_name
parser_version
status
error_code
elapsed_ms
row_count
```

Do not log:

- full bank statement text;
- full extracted tables;
- full card/account numbers;
- secrets/tokens;
- raw uploaded document contents;
- sensitive descriptions unless explicitly sanitized.

---

## 20. Testing Strategy

Prioritize tests for financial correctness, imports, workspace isolation, and
review/posting behavior.

Test levels:

```text
domain/unit:
  money parsing, Decimal conversion, date parsing, dedupe,
  validation, status policies, transfer rules

parser fixtures:
  parser detection, row count, first/last rows, totals,
  problematic rows, sanitized real statement shapes

application/integration:
  upload -> parse attempt -> raw transactions
  validation failure -> requires_review
  confirm row -> Operation + MoneyEntry
  repeat upload -> duplicate handling
  workspace isolation

template/presentation:
  ViewModel fields, action policy, HTMX partial rendering,
  review item states
```

Decorative UI tests are less important than correctness and review workflow
tests.

---

## 21. Migration Policy

Use Alembic for schema changes.

Rules:

- Every database-affecting model change needs a migration.
- Migrations must be deterministic and reviewable.
- Do not edit shared old migrations.
- Seed data must be idempotent.
- Do not hide schema changes in application startup unless explicitly
  documented.

---

## 22. Security Rules

Booker Tee handles sensitive financial data.

Rules:

- No external AI/document processing APIs by default.
- No sending uploaded PDFs to third-party services by default.
- No workspace data access without membership checks.
- No global object lookup by id alone for workspace-owned data.
- No full bank statement dumps in logs.
- No full card/account numbers in database or logs.
- External services require explicit product and user-level consent.

---

## 23. Performance Guidelines

Simple is fine, careless is not.

Use:

- pagination for raw transactions and operations;
- indexes on workspace-owned foreign keys;
- indexes on document/status fields;
- indexes on dedupe hashes;
- streaming/chunked file handling if uploads grow.

Do not add complex caching before ledger and import correctness are stable.

---

## 24. Quality Commands

Use Astral tooling:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

Before finishing coding tasks, run relevant checks. If infrastructure is missing,
say that clearly.

---

## 25. Architecture Decision Filter

Before adding a new component, ask:

1. Does this improve financial correctness, import reliability, review clarity,
   or workspace safety?
2. Does it preserve raw source data?
3. Does it reduce the chance of double-counting money?
4. Does it keep dependencies explicit?
5. Does it have a clear owner: service, use case, policy, presenter, repository,
   or adapter?
6. Does it reuse an existing concept instead of duplicating logic?
7. Is it a real abstraction with repeated stable use, or premature cleverness?

If the answer is weak, defer it or keep the implementation local and simple.

---

## 26. Anti-Patterns

Avoid:

```text
Parser directly inserts Operation rows.
Parser directly changes account balances.
Raw source data is discarded after parsing.
Financial rows are confirmed without review.
Workspace-owned objects are fetched by id alone.
Money is stored or calculated with float.
Transfers are counted as income or expense.
Business rules live in Jinja templates.
Routers contain parsing or ledger posting workflows.
Repository methods commit hidden transactions.
One service.py grows into a 1500-line mixed-responsibility file.
Dynamic import magic hides dependencies.
Free-floating business action functions make ownership unclear.
Every feature imports every other feature directly.
Celery is introduced before a synchronous service works.
AI/RAG/Text-to-SQL is added before the ledger is reliable.
```
