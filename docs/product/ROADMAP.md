# ROADMAP.md — Booker Tee

Product and engineering roadmap for Booker Tee.

```text
Status: planning reference
Read when: deciding sequencing after the current focused work
Do not use as: current sprint/task checklist
```

Read together with:

- [`PROJECT_VISION.md`](PROJECT_VISION.md) — product positioning and target users.
- [`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md) — canonical entities and invariants.
- [`ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) — code architecture and data flow.
- [`DESIGN.md`](../design/DESIGN.md) — UI/UX principles.
- [`FRONTEND_NEXT_DESIGN.md`](../design/FRONTEND_NEXT_DESIGN.md) — active
  frontend/SSR architecture and migration strategy.
- [`REFACTOR_PROJECT_DESIGN.md`](../design/REFACTOR_PROJECT_DESIGN.md) —
  historical reference for legacy frontend behavior.
- [`AGENTS.md`](../../AGENTS.md) — instructions for Codex and coding agents.

---

## Roadmap Thesis

Booker Tee grows from a narrow, reliable import wedge into a broader financial
clarity tool.

The wedge:

```text
Bank statement -> trusted financial data
```

The long-term product:

```text
Financial flows + accounts + properties + documents + collaboration + reports + automation
```

Use the principle:

```text
Parser-first, ledger-ready, automation-later.
```

This means:

1. First, make imported money trustworthy.
2. Then, make it understandable.
3. Then, make it collaborative.
4. Then, make it automated.
5. Then, make it intelligent.

---

## Guardrails

Every roadmap decision must preserve these invariants:

```text
1. Raw imported data is preserved.
2. Parser output requires review before ledger posting.
3. Internal transfers do not count as income, expense, profit, or property ROI.
4. Money uses Decimal / Numeric, never float.
5. Duplicate imports must not double-count money.
6. Every workspace-owned query is scoped by workspace_id.
7. Private financial data is not sent to external AI/API services unless explicitly requested.
```

Do not prioritize broad platform features before the user can trust the core
import/review/ledger flow.

---

## Current Assessment

The original parser-first MVP is complete and exceeded.

Completed or substantially implemented:

- Project foundation: FastAPI, PostgreSQL, SQLAlchemy, Alembic, uv, pytest.
- Workspace/user/account foundation.
- PDF/XLSX upload and local document storage.
- `UploadedDocument`, `ParseAttempt`, `RawTransaction`.
- Raw extraction, normalization, validation, review, and ledger posting.
- `Operation + MoneyEntry` ledger model.
- Account balances from ledger entries.
- Deduplication, duplicate states, reparsing, and parser failure handling.
- Minimal categories, properties, reports.
- Manual operations and transfers.
- Transaction rules and review suggestions.
- Unknown statement mapping flow.
- Workspace membership/invitation basics.
- Chat integration groundwork.
- UI/design audit tooling.

This means the roadmap is no longer a first-MVP task sequence. It is a planning
reference for what to improve next.

---

## Current Active Focus

### 1. Isolated Frontend Next

Source of truth:
[`FRONTEND_NEXT_DESIGN.md`](../design/FRONTEND_NEXT_DESIGN.md).

Goal:

```text
existing behavior audit
  -> isolated SSR web adapter
  -> vertical workflow migration
  -> legacy presentation cleanup
```

Why now:

- Repeated UI patterns need one controlled foundation without extending legacy
  CSS and templates.
- Backend, financial invariants and application use cases can remain stable
  while presentation workflows migrate independently.
- An isolated web adapter keeps a future JSON API or external frontend possible
  without building either prematurely.

Non-goals for this focus:

- Do not change financial meaning for visual reasons.
- Do not build React or a speculative API now.
- Do not reuse legacy CSS, base templates or presentation partials in the new
  adapter.
- Do not migrate all workflows in one uncontrolled rewrite.

### 2. Documentation Cleanup

Goal:

```text
shorter active docs
clear document status
historical MVP/roadmap preserved as guardrails
less context overload for future work
```

Rules:

- Do not create new docs unless they reduce total confusion.
- Prefer updating existing docs first.
- Mark historical documents clearly.
- Keep active implementation plans small enough to act on.

### 3. Import Reliability And Parser Coverage

Goal:

```text
More real statements
  -> better parser detection/mapping
  -> safer review
  -> less manual cleanup
```

Next useful work:

- Harden unknown statement mapping.
- Expand real bank fixtures.
- Improve parser diagnostics without exposing sensitive data.
- Keep parser output review-first.

---

## Near-Term Priorities

1. Build the minimal isolated Frontend Next foundation and manual-ledger pilot.
2. Validate the Workbench Row contract on a second workflow before broad reuse.
3. Tighten parser reliability for real user statements.
4. Improve reports where they answer regular weekly questions.
5. Simplify documentation and remove obsolete task-plan noise.
6. Prepare deployment/productization basics: backups, production settings,
   export, security review, operational runbooks.

---

## Mid-Term Priorities

### Parser Expansion

Useful when the current import/review workflow remains stable.

Deliverables:

- More bank and statement types.
- Parser registry/factory improvements.
- Configurable mapping templates where practical.
- Fixture library for real/sanitized statements.
- Better diagnostics for parser failures.

### Review And Rule Memory

Deliverables:

- Clearer rule suggestions.
- Better action policy for suggested/duplicate/confirmed/matched states.
- Safer bulk actions only after row-level correctness is strong.
- Rule creation from repeated user decisions.

### Collaboration

Deliverables:

- Stronger workspace roles and permissions.
- Clearer member/invitation flows.
- Audit trail for sensitive financial actions.
- Privacy-aware upload/review roles.

### Chat And Delivery Channels

Deliverables:

- Keep chat integrations provider-neutral.
- Chat upload/review must reuse the same import pipeline.
- Button-first, permission-checked review actions.
- Sensitive summaries hidden in shared channels by default.
- Email/IMAP only after the web and chat flows are reliable.

### Productization

Deliverables:

- Production settings hardening.
- Backup/restore documentation and tests.
- Export important financial data.
- Error pages and structured logs.
- Security review.

---

## Later Priorities

These are valid, but should remain parked until the structured data and review
workflow are dependable.

### Property Management Depth

Do later:

- Tenant records.
- Rent schedules.
- Security deposit liability workflow.
- Vacancy periods.
- Utility and meter readings.
- Property documents.
- Deeper property reports and ROI.

Guardrail:

```text
Tenant security deposits are not income until retained.
```

### Automation And Forecasting

Do later:

- Recurring transaction detection.
- Scheduled payments.
- Cash gap calendar.
- Receivables/payables.
- Virtual envelopes.
- Forecasted account balances.

Guardrail:

```text
Forecasts must distinguish confirmed history from projected future.
```

### AI, RAG, And Text-to-SQL

Do later:

- Local embeddings.
- RAG over documents and transaction descriptions.
- Read-only Text-to-SQL prototype.
- Query preview and confirmation.
- Source citations for numeric answers.

Guardrails:

```text
AI must not silently mutate financial data.
AI-generated SQL must be read-only by default.
AI answers about numbers must cite source records or generated SQL.
External AI APIs must not receive private financial data unless explicitly enabled.
```

---

## Parking Lot

Parked until the core flow is stable enough:

```text
advanced AI assistant
local LLM deployment
RAG over all documents
Text-to-SQL analytics
Telegram Mini App
mobile app
tenant portal
invoice generation
tax reports
full accounting exports
OCR for scanned receipts
bank API integrations
multi-currency investment tracking
complex chart dashboards
budget planning system
enterprise RBAC
subscription billing
```

Parking a feature does not mean rejecting it. It means protecting the product
from becoming broad before it is trustworthy.

---

## Decision Filter

Before adding a feature to active work, ask:

```text
1. Does it improve trusted statement-to-ledger import?
2. Does it improve financial correctness?
3. Does it reduce review friction?
4. Does it prevent duplicate or wrong money records?
5. Does it help the user understand cashflow, balances, properties, or results?
6. Can it be implemented without weakening workspace boundaries?
7. Can it be tested with real or sanitized data?
8. Is it needed before the current active focus is complete?
```

If the answer to question 8 is no, the feature probably belongs later.

---

## Current Mantra

```text
Make review clear.
Keep ledger correct.
Reduce template noise.
Then expand.
```
