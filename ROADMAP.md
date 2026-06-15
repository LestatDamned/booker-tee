# ROADMAP.md — Booker Tee

Product and engineering roadmap for Booker Tee.

This document defines the preferred order of product evolution. It should be read together with:

- `PROJECT_VISION.md` — product positioning and target users;
- `MVP.md` — parser-first MVP scope;
- `DOMAIN_MODEL.md` — canonical entities and invariants;
- `ARCHITECTURE.md` — code architecture and data flow;
- `AGENTS.md` — instructions for Codex and coding agents.

---

## 1. Roadmap thesis

Booker Tee should grow from a narrow, reliable wedge into a broader financial clarity platform.

The wedge is:

```text
Bank PDF statement -> trusted financial data
```

The long-term product is:

```text
Financial flows + accounts + properties + documents + collaboration + reports + automation
```

The roadmap must protect the product from becoming too broad too early.

Use the principle:

```text
Parser-first, ledger-ready, automation-later.
```

This means:

1. First, prove reliable PDF import on real bank statements.
2. Then, post confirmed rows into a correct ledger model.
3. Then, improve review, deduplication, reports, and rules.
4. Only after the core is reliable, add collaboration, Telegram, email, property operations, and AI.

---

## 2. Roadmap guardrails

### 2.1 This is not a date-based roadmap

This roadmap is phase-based, not calendar-based.

Do not move to the next phase because of time pressure. Move to the next phase only when the current phase passes its acceptance criteria.

### 2.2 Do not skip the PDF reliability phase

The first major risk is not UI, charts, AI, or property management.

The first major risk is:

```text
Can Booker Tee reliably parse real bank PDF statements and produce trustworthy financial rows?
```

Do not start broad product features before this is validated.

### 2.3 Keep future features visible but out of MVP

The roadmap includes future modules such as Telegram import, IMAP email import, advanced property management, RAG, Text-to-SQL, and collaboration.

These are important, but they must not enter the first MVP unless the user explicitly changes priorities.

### 2.4 Every phase must preserve financial correctness

Do not trade correctness for speed.

Core invariants:

```text
1. Raw imported data is preserved.
2. Parser output requires review before ledger posting.
3. Internal transfers do not count as income, expense, profit, or property ROI.
4. Money uses Decimal / Numeric, never float.
5. Duplicate imports must not double-count money.
6. Every workspace-owned query is scoped by workspace_id.
```

---

## 3. Strategic phases overview

```text
Phase 0  — Project foundation
Phase 1  — Parser Lab: PDF intake and raw extraction
Phase 2  — RawTransaction and normalization
Phase 3  — Statement validation and review screen
Phase 4  — Ledger posting: Operation + MoneyEntry
Phase 5  — Deduplication, reparsing, and reliability hardening
Phase 6  — Minimal categories, properties, and useful reports
Phase 7  — Manual operations and transfer matching
Phase 8  — More banks and parser configuration system
Phase 9  — Workspace collaboration and roles
Phase 10 — Telegram and email delivery channels
Phase 11 — Property management depth
Phase 12 — Automation and financial forecasting
Phase 13 — AI memory, RAG, and Text-to-SQL
Phase 14 — Productization, deployment, and polish
```

The first real MVP ends around Phase 6.

---

## 4. Phase 0 — Project foundation

### Goal

Create a clean, maintainable FastAPI application skeleton that follows the project architecture and is ready for the PDF-first MVP.

### User value

No direct user value yet. This phase exists to avoid technical chaos later.

### Main deliverables

```text
1. FastAPI project skeleton
2. PostgreSQL connection
3. SQLAlchemy 2.0 async setup
4. Alembic migrations
5. Pydantic v2 schemas
6. Jinja2 templates setup
7. HTMX-ready base layout
8. Tailwind setup
9. uv-based dependency management
10. Ruff and ty configured
11. Test infrastructure
12. Healthcheck endpoint
```

### Recommended Codex tasks

```text
1. Create project structure according to ARCHITECTURE.md.
2. Add pyproject.toml with uv, ruff, ty, pytest configuration.
3. Add application settings module.
4. Add database session management.
5. Add SQLAlchemy Base and Alembic.
6. Add base HTML layout.
7. Add smoke tests for app startup and healthcheck.
```

### Acceptance criteria

```text
1. uv sync works.
2. uv run ruff check . works.
3. uv run ruff format . works.
4. uv run ty check . works or has a documented temporary baseline.
5. uv run pytest works.
6. FastAPI app starts locally.
7. Database migration can be generated and applied.
```

### Explicit non-goals

```text
PDF parsing
auth complexity
manual finance tracker
reports
property management
AI
Telegram
email import
```

---

## 5. Phase 1 — Parser Lab: PDF intake and raw extraction

### Goal

Build the first vertical slice for uploading a real bank PDF and seeing what the system can extract from it.

This phase is exploratory but must store everything cleanly.

### User value

The user can upload a bank statement and inspect the raw extracted structure.

### Main deliverables

```text
1. Minimal User model
2. Minimal Workspace model
3. WorkspaceMember model
4. Automatic personal workspace for the first user
5. Minimal Account model
6. UploadedDocument model
7. PDF upload endpoint/page
8. File storage for uploaded PDFs
9. ParseAttempt model
10. pdfplumber raw table extraction
11. Raw extracted tables/text saved as JSON
12. Debug document detail page
```

### Data flow

```text
PDF upload
  -> UploadedDocument(status=uploaded)
  -> ParseAttempt(status=running)
  -> pdfplumber extraction
  -> ParseAttempt.extracted_payload_json
  -> UploadedDocument(status=parsed_raw or failed_to_parse)
```

### Recommended Codex tasks

```text
1. Implement User, Workspace, WorkspaceMember models.
2. Implement Account model with account type enum.
3. Implement UploadedDocument model and migration.
4. Implement local file storage service.
5. Implement upload form and route.
6. Implement ParseAttempt model.
7. Implement simple parser service that extracts tables with pdfplumber.
8. Save extracted tables and text to JSON.
9. Add a document detail page that shows parse status and raw extracted output.
```

### Acceptance criteria

```text
1. A real PDF can be uploaded.
2. The original file is preserved.
3. A ParseAttempt is created for each parser run.
4. Extracted raw tables are saved.
5. Parser errors are stored and displayed without crashing the app.
6. The user can open the document detail page and inspect raw output.
```

### Explicit non-goals

```text
RawTransaction normalization
ledger posting
income/expense reports
categories
property linking
advanced parser configs
background jobs
```

---

## 6. Phase 2 — RawTransaction and normalization

### Goal

Transform raw extracted table rows into structured draft rows while preserving the raw source payload.

### User value

The user can see parsed transaction-like rows instead of only raw table matrices.

### Main deliverables

```text
1. RawTransaction model
2. Raw row extraction from parser payload
3. Parser interface for one first bank/statement type
4. Normalized date parsing
5. Normalized Decimal amount parsing
6. Currency detection
7. Direction detection: inflow / outflow
8. Description normalization
9. Row-level status: pending / normalized / needs_review / failed
10. Raw payload preservation for every row
```

### Data flow

```text
ParseAttempt.extracted_payload_json
  -> bank-specific parser
  -> RawTransaction rows
  -> normalized fields
  -> row-level statuses
```

### Recommended Codex tasks

```text
1. Add RawTransaction model and migration.
2. Define parser interface/protocol.
3. Implement first bank parser for one real statement format.
4. Add normalizers for dates, amounts, and currency.
5. Store raw_payload for every extracted row.
6. Add document detail table with raw transaction rows.
7. Add row statuses and error messages.
8. Add tests with PDF fixtures or extracted payload fixtures.
```

### Acceptance criteria

```text
1. One real bank statement produces RawTransaction rows.
2. Date values are parsed into date fields when possible.
3. Amounts are parsed into Decimal-compatible values.
4. Raw strings are preserved.
5. Unclear rows are marked needs_review, not silently dropped.
6. Parser unit tests cover representative rows.
```

### Explicit non-goals

```text
automatic confirmed accounting
full multi-bank support
manual operations UI
complex categories
AI extraction
```

---

## 7. Phase 3 — Statement validation and review screen

### Goal

Make imported rows trustworthy by validating totals and giving the user a clear review workflow.

### User value

The user can understand whether the import is reliable before confirming anything into the ledger.

### Main deliverables

```text
1. Statement summary extraction where available
2. Opening balance extraction where available
3. Closing balance extraction where available
4. Total inflow extraction where available
5. Total outflow extraction where available
6. Calculated totals from RawTransaction rows
7. Validation status: valid / mismatch / unavailable / needs_review
8. Review screen for imported rows
9. Row actions: confirm, ignore, mark needs_review
10. Document-level status transitions
```

### Data flow

```text
RawTransaction rows
  -> calculated totals
  -> compare with statement totals
  -> validation result
  -> review screen
```

### Recommended Codex tasks

```text
1. Extend ParseAttempt with statement totals fields.
2. Add validation service.
3. Add calculated totals from RawTransaction.
4. Add document validation status.
5. Build review screen with HTMX row actions.
6. Add confirm/ignore preliminary actions without ledger posting if needed.
7. Add tests for matched and mismatched totals.
```

### Acceptance criteria

```text
1. The document page shows extracted count, inflow, outflow, and validation status.
2. If statement totals are available and mismatch, the document requires review.
3. Mismatched documents are not posted automatically.
4. The user can see which rows need attention.
5. No raw row is lost during validation.
```

### Explicit non-goals

```text
advanced reports
automated categorization
multi-user review workflow
AI-based validation
```

---

## 8. Phase 4 — Ledger posting: Operation + MoneyEntry

### Goal

Convert reviewed RawTransaction rows into confirmed financial records using the canonical ledger model.

### User value

The user can turn imported bank statement rows into real account movements and balances.

### Main deliverables

```text
1. Operation model
2. MoneyEntry model
3. Posting service
4. Confirm raw row into Operation + MoneyEntry
5. Atomic database transaction for posting
6. linked_operation_id on RawTransaction
7. Account balance calculation from MoneyEntry
8. Basic account detail page with posted entries
```

### Data flow

```text
RawTransaction(status=ready_to_confirm)
  -> user confirms
  -> Operation(type=income/expense, source=bank_pdf)
  -> MoneyEntry(account_id, signed amount)
  -> RawTransaction(status=confirmed, linked_operation_id=...)
```

### Recommended Codex tasks

```text
1. Implement Operation model and migration.
2. Implement MoneyEntry model and migration.
3. Implement posting service with transaction boundaries.
4. Add confirm action on review screen.
5. Add account balance query.
6. Add account detail page with posted money entries.
7. Add tests for income, expense, and failed posting rollback.
```

### Acceptance criteria

```text
1. Confirming a raw row creates exactly one Operation.
2. Confirming a raw row creates the correct MoneyEntry.
3. Posting is atomic.
4. Re-confirming the same raw row is blocked.
5. Account balance is calculated from MoneyEntry, not manually mutated.
6. Parser code does not create Operation directly.
```

### Explicit non-goals

```text
transfer matching
manual operations UI
property ROI
complex dashboards
```

---

## 9. Phase 5 — Deduplication, reparsing, and reliability hardening

### Goal

Prevent duplicate imports and make parser failures recoverable.

### User value

The user can safely upload statements multiple times or fix a parser without corrupting financial records.

### Main deliverables

```text
1. dedupe_hash for RawTransaction and/or Operation
2. Duplicate detection during import
3. Duplicate status on review screen
4. Reparse action for UploadedDocument
5. ParseAttempt history per document
6. Safe parser error handling
7. Import idempotency rules
8. Validation hardening
```

### Recommended Codex tasks

```text
1. Design dedupe hash fields.
2. Add unique indexes where safe.
3. Add possible_duplicate status.
4. Add repeated upload tests.
5. Implement reparse action that creates a new ParseAttempt.
6. Ensure old raw data is preserved or superseded safely.
7. Add parser error fixtures.
```

### Acceptance criteria

```text
1. Re-uploading the same PDF does not double-count money.
2. Overlapping statement periods produce visible duplicate warnings.
3. Failed parsing does not delete the uploaded file.
4. Reparse creates a new ParseAttempt and preserves history.
5. Parser errors are visible and actionable.
```

### Explicit non-goals

```text
support for all banks
automatic correction of all parser failures
AI parser repair
```

---

## 10. Phase 6 — Minimal categories, properties, and useful reports

### Goal

Add the first layer of practical financial meaning after the PDF-to-ledger flow works.

### User value

The user can start answering basic questions:

```text
Where did money go?
Which income belongs to which property?
What is the simple result for this account or property?
```

### Main deliverables

```text
1. Minimal Category seed per workspace
2. Category assignment on review/posting
3. Minimal Property model
4. Optional property assignment on operation
5. Basic reports:
   - account balance
   - income vs expense by period
   - uncategorized operations
   - property income/expense summary
6. Report filters by workspace, account, category, property, period
```

### Recommended Codex tasks

```text
1. Add Category model if not already implemented.
2. Seed basic system categories.
3. Add category selection in review screen.
4. Add minimal Property model with name only.
5. Add property selection in review screen.
6. Add simple reports page.
7. Add tests for property ROI excluding transfers.
```

### Acceptance criteria

```text
1. Confirmed operations can be categorized.
2. Confirmed operations can optionally link to a property.
3. Transfers do not affect income/expense reports.
4. Property summary includes only property-linked profit-affecting operations.
5. Reports are scoped by workspace_id.
```

### Explicit non-goals

```text
full category tree UI
tenant management
security deposit workflow
meter readings
advanced charts
cashflow forecasting
```

---

## 11. MVP exit criteria

The first MVP is considered complete when all of these are true:

```text
1. One real bank PDF statement format is supported end-to-end.
2. The original uploaded PDF is preserved.
3. Each parser run is stored as a ParseAttempt.
4. Raw extracted tables/text are preserved.
5. RawTransaction rows are created from extracted data.
6. Dates, amounts, currency, and descriptions are normalized where possible.
7. Statement totals are validated when available.
8. The review screen shows rows, statuses, totals, and warnings.
9. The user can confirm rows into Operation + MoneyEntry.
10. Account balances are calculated from MoneyEntry.
11. Duplicate imports do not double-count money.
12. Parser failures do not crash the application or delete source files.
13. Basic category and optional property assignment works.
14. Simple reports provide useful financial clarity.
15. The code follows AGENTS.md, DOMAIN_MODEL.md, MVP.md, and ARCHITECTURE.md.
```

The MVP is not complete if it only extracts tables but cannot confirm rows into the ledger.

The MVP is also not complete if it creates operations automatically without review and validation.

---

## 12. Phase 7 — Manual operations and transfer matching

### Goal

Support money movements that do not come from PDF statements and correctly classify internal transfers.

### User value

The user can track cash, deposits, transfers, and movements between accounts without double-counting income.

### Main deliverables

```text
1. Manual income operation form
2. Manual expense operation form
3. Manual transfer operation form
4. Cash account use cases
5. Transfer matching suggestions from imported rows
6. Mark raw bank row as transfer from/to another account
7. Internal transfer reports excluded from profit
```

### Key user scenario

```text
1. Received cash rent for property "9 Maya 20".
2. Deposited cash to a card.
3. Transferred money from card to deposit.
```

Correct accounting:

```text
cash rent income      -> income, affects_profit=true, property_id set
cash deposit to card  -> transfer, affects_profit=false
card to deposit       -> transfer, affects_profit=false
```

### Acceptance criteria

```text
1. Manual transfer creates one Operation and two MoneyEntry rows.
2. Internal transfers do not appear as income or expense.
3. Transfer matching can suggest likely pairs by amount/date/account.
4. The user can manually override matching decisions.
```

---

## 13. Phase 8 — More banks and parser configuration system

### Goal

Expand import reliability beyond one bank/statement format.

### User value

The product becomes useful for users with multiple cards, accounts, deposits, and banks.

### Main deliverables

```text
1. Parser registry/factory
2. Bank and statement type detection
3. Parser config files in YAML/JSON
4. Second bank parser
5. Third statement type parser, e.g. deposit or checking account
6. Parser fixture library
7. Parser diagnostics UI
```

### Recommended parser config direction

```text
parsers/
  tbank_card.yaml
  tbank_deposit.yaml
  sber_card.yaml
  alfa_card.yaml
```

### Acceptance criteria

```text
1. Parser selection does not rely on a single hardcoded parser.
2. At least two statement formats work end-to-end.
3. Parser configs can adjust column mapping without changing core posting code.
4. Each parser has fixtures and tests.
```

---

## 14. Phase 9 — Workspace collaboration and roles

### Goal

Allow multiple people to participate in a workspace without breaking privacy boundaries.

### User value

Family members, assistants, partners, or property managers can help with data input and review.

### Main deliverables

```text
1. Workspace switcher UI
2. Create additional workspaces
3. Invite users by email or invite link
4. Roles: owner, admin, editor, viewer, uploader, analyst
5. Permission checks
6. Audit log for sensitive actions
7. Optional restricted document upload role
```

### Acceptance criteria

```text
1. A user can belong to multiple workspaces.
2. Every workspace-owned query is scoped correctly.
3. A viewer cannot mutate financial records.
4. An uploader can upload documents without seeing sensitive reports if configured.
5. Audit log records important financial actions.
```

### Explicit non-goals

```text
enterprise SSO
complex organization hierarchy
fine-grained custom roles UI
```

---

## 15. Phase 10 — Telegram and email delivery channels

### Goal

Add convenient ways to deliver statements, checks, and documents into Booker Tee.

### User value

The user does not have to manually open the web app every time. They can forward files from familiar tools.

### Main deliverables

```text
1. Telegram bot file upload
2. Telegram user to Booker Tee user mapping
3. Workspace selection for Telegram uploads
4. Email/IMAP attachment collector
5. Source channel metadata on UploadedDocument
6. Duplicate file protection across channels
7. Background processing for uploads
```

### Acceptance criteria

```text
1. A PDF forwarded to the Telegram bot creates UploadedDocument.
2. An email attachment can create UploadedDocument.
3. Uploaded documents enter the same parser pipeline as web uploads.
4. The parser pipeline does not fork into separate channel-specific logic.
```

### Explicit non-goals

```text
Telegram Mini App
AI chat inside Telegram
full document management
```

---

## 16. Phase 11 — Property management depth

### Goal

Turn properties into useful financial centers without becoming a full property management ERP.

### User value

DIY landlords can understand actual property performance, not just gross rent.

### Main deliverables

```text
1. Property profile details
2. Tenant records
3. Rent schedule
4. Security deposit tracking
5. Vacancy periods
6. Utility and meter readings
7. Property document attachments
8. Property-level reports
9. ROI and cashflow metrics
```

### Important accounting rule

Security deposits are not income until retained.

```text
tenant deposit received -> liability / non-profit movement
deposit returned         -> liability settlement
deposit retained         -> income or damage compensation, depending on classification
```

### Acceptance criteria

```text
1. Property report separates rent income, operating expenses, deposits, and transfers.
2. Vacancy metrics affect property performance reporting.
3. Property documents can be linked without bloating the core ledger.
```

---

## 17. Phase 12 — Automation and financial forecasting

### Goal

Help users understand future financial pressure, not only past transactions.

### User value

The user can see upcoming cash gaps, recurring obligations, debts, and planned payments.

### Main deliverables

```text
1. Recurring transaction detection
2. Scheduled payments
3. Cash gap calendar
4. Debt tracking: receivables and payables
5. Virtual envelopes / subaccounts
6. Forecasted account balances
7. Alerts for upcoming negative balance risk
```

### Acceptance criteria

```text
1. Recurring transactions can generate future projections.
2. Forecasts distinguish confirmed history from projected future.
3. Debts do not incorrectly appear as normal expenses.
4. Virtual envelopes do not corrupt physical account balances.
```

---

## 18. Phase 13 — AI memory, RAG, and Text-to-SQL

### Goal

Add intelligence after the structured financial database is reliable.

### User value

The user can ask natural-language questions and find documents, transactions, and financial explanations faster.

### Main deliverables

```text
1. Local embeddings for documents and transaction descriptions
2. pgvector storage
3. RAG search over documents and transaction text
4. Safe Text-to-SQL prototype
5. Query preview and confirmation
6. Read-only SQL execution mode
7. AI answer citations to source records
8. Privacy-first local model support
```

### Safety and correctness rules

```text
1. AI must not silently mutate financial data.
2. AI-generated SQL must be read-only by default.
3. AI answers about numbers must cite exact source records or generated SQL.
4. AI must not replace statement validation or user review.
5. External AI APIs must not receive private financial data unless explicitly enabled by the user.
```

### Acceptance criteria

```text
1. User can semantically search documents and transaction descriptions.
2. User can ask basic read-only analytic questions.
3. AI output is traceable to source records.
4. Incorrect or uncertain answers are clearly marked.
```

---

## 19. Phase 14 — Productization, deployment, and polish

### Goal

Prepare Booker Tee for real daily use.

### User value

The product becomes stable, deployable, understandable, and pleasant to use.

### Main deliverables

```text
1. Docker Compose for app + PostgreSQL + Redis if needed
2. Production settings
3. Backup strategy
4. File storage strategy
5. Import/export
6. Better onboarding
7. UI polish
8. Responsive mobile layout
9. Error pages
10. Observability and structured logs
11. Security review
12. Data deletion/export controls
```

### Acceptance criteria

```text
1. A fresh environment can be deployed from documentation.
2. Backups are documented and tested.
3. User can export important financial data.
4. UI supports real daily workflows without debug-only screens.
```

---

## 20. Priority queue after the first MVP

After the first MVP, prioritize based on real user pain.

Recommended priority order:

```text
1. More reliable parser support for the user’s real banks
2. Deduplication and transfer matching
3. Minimal reports users actually check weekly
4. Transaction rules and categorization memory
5. Manual operations for cash and transfers
6. Property linking and landlord reports
7. Telegram upload convenience
8. Workspace collaboration
9. Email import
10. Forecasting and debts
11. AI/RAG/Text-to-SQL
```

Do not prioritize AI before the user trusts the underlying data.

---

## 21. Feature parking lot

These ideas are valid but should stay parked until the core flow is stable:

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

Parking a feature does not mean rejecting it. It means protecting the MVP.

---

## 22. Decision filter for roadmap changes

Before adding any feature to the active roadmap, ask:

```text
1. Does it improve trusted PDF-to-ledger import?
2. Does it improve financial correctness?
3. Does it reduce review friction?
4. Does it prevent duplicate or wrong money records?
5. Does it help the target user understand cashflow, balances, properties, or results?
6. Can it be implemented without weakening workspace boundaries?
7. Can it be tested with real data?
8. Is it needed before the current phase acceptance criteria are met?
```

If the answer to question 8 is no, the feature probably belongs in a later phase.

---

## 23. Suggested first Codex epic

The first Codex epic should be:

```text
Implement the first complete PDF statement import flow for one bank.
```

Scope:

```text
1. Upload PDF
2. Store UploadedDocument
3. Create ParseAttempt
4. Extract raw tables with pdfplumber
5. Store raw JSON
6. Create RawTransaction rows
7. Normalize date, amount, currency, description
8. Validate totals when available
9. Show review screen
10. Confirm row into Operation + MoneyEntry
11. Calculate account balance
12. Prevent duplicate confirmation
```

Out of scope:

```text
full manual tracker
advanced property management
Telegram/email import
AI
complex dashboards
multi-bank support beyond the first parser
```

---

## 24. Final roadmap mantra

```text
First make imported money trustworthy.
Then make it understandable.
Then make it collaborative.
Then make it automated.
Then make it intelligent.
```

