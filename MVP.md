# MVP.md — Booker Tee

Parser-first MVP specification for Booker Tee.

This document defines the first useful product version. It should be read together with:

- `PROJECT_VISION.md` — product positioning and target audience;
- `DOMAIN_MODEL.md` — canonical entities and invariants;
- `ARCHITECTURE.md` — project structure and engineering architecture;
- `AGENTS.md` — instructions for Codex and other coding agents.

---

## 1. MVP thesis

The first MVP is **not** a complete personal finance tracker.

The first MVP is a reliable pipeline that turns real bank PDF statements into trusted financial records:

```text
PDF bank statement
  -> uploaded source document
  -> parser attempt
  -> raw extracted tables
  -> raw transactions
  -> normalized draft rows
  -> validation and deduplication
  -> review screen
  -> confirmed Operation + MoneyEntry records
  -> account balance and simple reports
```

The key product hypothesis:

> Booker Tee can reliably transform real bank PDF statements into clean, reviewable, validated financial data without losing raw source information or double-counting money.

Use the principle:

```text
Parser-first, ledger-ready.
```

This means the implementation should prioritize the PDF import pipeline, but confirmed rows must still be posted into the correct financial model: `Operation 1 -> N MoneyEntry`.

---

## 2. Target users for the MVP

The MVP is for financially aware users who already care about financial clarity but do not want heavy accounting software.

Primary MVP users:

```text
1. Financially aware individuals
2. DIY landlords
3. Small entrepreneurs
4. Microbusiness owners
5. Small business operators
```

They need practical financial clarity, not statutory accounting.

They want to answer:

```text
Where did the money come from?
Where did the money go?
Where is the money now?
Can I trust the imported data?
Which transactions need review?
Did I accidentally import the same money twice?
```

For the MVP, the most important user pain is:

```text
Bank statements exist as PDFs, but the user needs clean transactions, balances, and reviewable records.
```

---

## 3. Product positioning of the MVP

MVP positioning:

> Booker Tee imports bank PDF statements, preserves raw source data, extracts and validates transactions, lets the user review them, and posts confirmed rows into a simple financial ledger.

Do not position the MVP as:

```text
AI accounting platform
full bookkeeping software
property management suite
ERP
tax reporting tool
family budgeting app
Telegram-first product
RAG knowledge base
```

Those can become future layers after the PDF-to-ledger flow works reliably.

---

## 4. MVP success criteria

The MVP is successful when it can process real PDF statements from one bank and produce trusted financial data.

Minimum success criteria:

```text
1. A user can upload a PDF statement for one supported bank/type.
2. Booker Tee stores the original file and metadata.
3. Booker Tee creates a ParseAttempt for every parser run.
4. Booker Tee extracts raw table data and preserves it as JSON.
5. Booker Tee creates RawTransaction rows from extracted data.
6. Booker Tee normalizes dates, amounts, currency, and descriptions.
7. Booker Tee validates statement totals when the PDF contains them.
8. Booker Tee marks uncertain rows or mismatched statements as requiring review.
9. Booker Tee shows a review screen before confirmed posting.
10. The user can confirm, ignore, or mark raw rows as requiring review.
11. Confirmed raw rows create Operation + MoneyEntry records.
12. Account balances are calculated from MoneyEntry, not manually mutated.
13. Re-uploading the same statement does not double-count money.
14. Parser errors do not delete files or break the application.
15. There are parser tests with real or sanitized PDF fixtures.
```

---

## 5. MVP non-goals

Do not build these before the first reliable PDF import flow exists:

```text
full manual finance tracker
full Category CRUD
full Property CRUD
tenant management
leases and contract storage
utility meters
vacancy metrics
workspace invitations UI
advanced RBAC UI
Telegram ingestion
IMAP ingestion
AI assistant
RAG
Text-to-SQL
pgvector integration
local LLM integration
advanced dashboards
cash-flow forecast
virtual envelopes
debt/liability module
SaaS billing
mobile app
Telegram Mini App
```

Important rule:

> Manual operations, property management, collaboration, and AI must not block the first working PDF-to-ledger flow.

---

## 6. Scope summary

### 6.1 In scope

```text
Project foundation
Minimal user/workspace boundary
Minimal account management
PDF upload
Document metadata storage
Parse attempts
First parser interface
First bank parser
Raw table extraction
Raw transaction storage
Raw transaction normalization
Statement validation
Review screen
Confirm-to-ledger flow
Balance calculation
Deduplication
Basic category seed
Optional minimal property link
Basic parser tests
```

### 6.2 Out of scope

```text
Multiple banks in the first milestone
Perfect autonomous parsing
Silent auto-confirmation
Complex role management
Beautiful dashboards
Full property management
AI interpretation
External bank API integration
Telegram/email import
Tax/accounting reports
```

---

## 7. Required MVP entities

The MVP should implement only the minimum useful subset of the domain model.

### 7.1 Required from the beginning

```text
User
Workspace
WorkspaceMember
Account
UploadedDocument
ParseAttempt
RawTransaction
Operation
MoneyEntry
```

### 7.2 Required but minimal

```text
Category
```

Use seeded categories only at first. Full category management can come later.

Suggested seed categories:

```text
Uncategorized
Income
Expense
Transfer
Adjustment
Bank fee
Rent
Utilities
Repair
Other
```

### 7.3 Optional in late MVP

```text
Property
```

Use only minimal fields:

```text
id
workspace_id
name
is_active
created_at
updated_at
```

Do not implement tenants, leases, photos, deposits, utility meters, vacancy, or ROI dashboards in the first MVP.

### 7.4 Not required in first MVP

```text
TransactionRule
```

Transaction rules should come after the review screen works. First, the user reviews and confirms. Then Booker Tee may suggest rules based on repeated decisions.

---

## 8. MVP implementation order

The implementation order is intentionally different from a generic finance tracker order.

Do not start by building a complete manual accounting UI.

Build the PDF pipeline first.

### Phase 1 — Project foundation

Goal: create a runnable, testable FastAPI project foundation.

Implement:

```text
FastAPI app skeleton
settings/config
PostgreSQL connection
SQLAlchemy async setup
Alembic setup
base model conventions
pytest setup
healthcheck endpoint
basic Jinja2 layout
basic HTMX support
```

Acceptance criteria:

```text
1. Application starts locally.
2. Database connection works.
3. Alembic can create and apply migrations.
4. Tests can run.
5. Healthcheck endpoint returns OK.
```

---

### Phase 2 — Minimal identity and workspace boundary

Goal: make the system workspace-aware from day one.

Implement:

```text
User model
Workspace model
WorkspaceMember model
automatic personal workspace for the first/local user
current_workspace dependency or service context
workspace_id on workspace-owned tables
```

MVP simplification:

```text
Full authentication can be simple in the first MVP.
A local/dev user is acceptable for the earliest parser lab.
But the database model must still be workspace-first.
```

Acceptance criteria:

```text
1. A user can exist.
2. A personal workspace is created automatically.
3. The owner has a WorkspaceMember record.
4. Workspace-owned queries are scoped by workspace_id.
```

---

### Phase 3 — Minimal accounts

Goal: create the account where imported statement rows will be posted.

Implement:

```text
Account model
create/list account flow
account type enum
currency
bank_name
account_number_last4 or account_number_mask
card_last4
initial_balance optional
is_active
```

Supported account types:

```text
cash
card
deposit
checking
other
```

Acceptance criteria:

```text
1. User can create an account in the current workspace.
2. User can select an account when uploading a PDF.
3. Account belongs to a workspace.
4. Account balances are not manually mutated by import logic.
```

---

### Phase 4 — PDF intake

Goal: safely store source PDF documents before parsing.

Implement:

```text
UploadedDocument model
PDF upload endpoint/page
file storage path
original filename
content type
file size
file hash
status
uploaded_by_user_id
workspace_id
account_id optional but recommended
```

Suggested statuses:

```text
uploaded
pending_parse
parsed
requires_review
failed_to_parse
confirmed
ignored
```

Acceptance criteria:

```text
1. User can upload a PDF.
2. Original file is saved.
3. File metadata is stored.
4. File hash is calculated.
5. Duplicate file hash is detected.
6. Failed parsing never deletes the source file.
```

---

### Phase 5 — ParseAttempt and raw table extraction

Goal: run a parser without losing raw output.

Implement:

```text
ParseAttempt model
parser status
parser name
parser version
started_at
finished_at
error_message
error_traceback optional
extracted_text optional
extracted_tables_json
```

Suggested statuses:

```text
pending
running
success
failed
requires_review
```

Parser approach:

```text
1. Use pdfplumber for table extraction.
2. Preserve extracted tables as JSON.
3. Do not create confirmed financial records at this stage.
4. If parsing fails, save the error in ParseAttempt.
```

Acceptance criteria:

```text
1. Every parse run creates a ParseAttempt.
2. Extracted tables are visible in a debug/document detail screen.
3. Parser errors are stored, not swallowed.
4. Reparse creates a new ParseAttempt.
```

---

### Phase 6 — Parser interface and first bank parser

Goal: support one real bank statement type end-to-end.

Implement parser interface:

```text
can_parse(document) -> bool
extract_tables(document) -> ExtractedTables
extract_statement_metadata(raw) -> StatementMetadata
extract_raw_transactions(raw) -> list[RawTransactionDraft]
normalize_raw_transaction(draft) -> NormalizedTransactionDraft
validate_statement(result) -> ValidationResult
```

Start with:

```text
one bank
one statement type
2-3 real or sanitized PDF fixtures
```

Do not implement multiple banks before one bank works end-to-end.

Acceptance criteria:

```text
1. Parser can identify supported statement files.
2. Parser can reject unsupported files gracefully.
3. Parser extracts transaction rows from real fixtures.
4. Parser preserves raw row payloads.
5. Parser has tests.
```

---

### Phase 7 — RawTransaction storage

Goal: store every extracted bank row before confirmation.

Implement:

```text
RawTransaction model
workspace_id
uploaded_document_id
parse_attempt_id
account_id
row_index
operation_date_raw
posting_date_raw optional
description_raw
amount_raw
currency_raw
balance_after_raw optional
raw_payload JSON
status
normalization_error optional
linked_operation_id nullable
```

Suggested statuses:

```text
new
normalized
needs_review
duplicate
ignored
confirmed
failed
```

Acceptance criteria:

```text
1. Extracted table rows become RawTransaction rows.
2. Raw payload is preserved.
3. Failed rows are stored with an error status.
4. No RawTransaction creates Operation automatically.
```

---

### Phase 8 — Normalization

Goal: convert raw bank strings into typed draft values.

Normalize:

```text
date strings -> date
amount strings -> Decimal
currency strings -> ISO-like currency code
description -> normalized searchable string
direction -> inflow/outflow
balance_after -> Decimal optional
```

Rules:

```text
Use Decimal/Numeric for money.
Never use float for money.
Preserve raw strings even after successful normalization.
Uncertain rows must be marked needs_review.
```

Acceptance criteria:

```text
1. Dates are parsed consistently.
2. Amounts are parsed as Decimal.
3. Income and expense directions are detected.
4. Invalid rows do not crash the import.
5. Invalid rows are visible to the user.
```

---

### Phase 9 — Statement validation

Goal: determine whether the imported statement can be trusted.

Extract when available:

```text
statement period start
statement period end
opening balance
closing balance
total inflow
total outflow
bank account/card hints
```

Validate:

```text
calculated total inflow == statement total inflow
calculated total outflow == statement total outflow
opening balance + inflow - outflow == closing balance
```

Validation result:

```text
valid
requires_review
failed
not_available
```

Rules:

```text
If control totals mismatch, do not auto-post rows.
If totals are unavailable, allow manual review but mark validation as not_available.
If validation fails, document status must be requires_review or failed_to_parse.
```

Acceptance criteria:

```text
1. Totals are extracted when present.
2. Calculated totals are stored.
3. Mismatches are shown to the user.
4. Mismatched documents cannot be silently confirmed.
```

---

### Phase 10 — Review screen

Goal: give the user control before posting anything to the ledger.

The document detail/review screen should show:

```text
Document name
Bank/parser name
Linked account
Statement period
Rows found
Rows normalized
Rows requiring review
Duplicate rows
Validation status
Control totals comparison
```

Table columns:

```text
Date
Description from bank
Amount
Direction
Status
Category optional
Property optional
Action
```

Required actions:

```text
Confirm row
Ignore row
Mark as needs review
Edit normalized fields
Confirm all valid rows
```

Optional late-MVP actions:

```text
Mark as transfer
Link to property
Set category
```

Acceptance criteria:

```text
1. User can inspect extracted rows before posting.
2. User can confirm valid rows.
3. User can ignore irrelevant rows.
4. User can see why a row needs review.
5. User cannot accidentally post failed rows.
```

---

### Phase 11 — Confirm raw rows into ledger

Goal: create confirmed financial records only after review.

Confirmed income/expense row creates:

```text
Operation
MoneyEntry
RawTransaction.linked_operation_id
RawTransaction.status = confirmed
```

For a bank card expense:

```text
Operation:
  type = expense
  affects_profit = true
  source = bank_pdf

MoneyEntry:
  account = selected account
  amount = negative Decimal
```

For a bank card income:

```text
Operation:
  type = income
  affects_profit = true
  source = bank_pdf

MoneyEntry:
  account = selected account
  amount = positive Decimal
```

For a transfer between own accounts:

```text
Operation:
  type = transfer
  affects_profit = false

MoneyEntry 1:
  source account
  amount = negative Decimal

MoneyEntry 2:
  destination account
  amount = positive Decimal
```

MVP simplification:

```text
Transfer detection can be manual in the first MVP.
Automatic transfer matching can come later.
```

Acceptance criteria:

```text
1. Confirmed raw rows create Operation + MoneyEntry.
2. Each confirmed row links back to its RawTransaction.
3. Re-confirming the same row is impossible.
4. Internal transfers do not affect profit.
5. Ledger posting happens inside one database transaction.
```

---

### Phase 12 — Balance calculation

Goal: show reliable balances from ledger entries.

Rules:

```text
Account balance = initial_balance + sum(MoneyEntry.amount for account)
Do not store mutable current_balance as the source of truth.
If current_balance is cached later, it must be derived and rebuildable.
```

Acceptance criteria:

```text
1. Account detail page shows calculated balance.
2. Balance changes after confirming rows.
3. Ignored raw rows do not affect balance.
4. Duplicate rows do not affect balance twice.
```

---

### Phase 13 — Deduplication and repeat-upload protection

Goal: prevent double-counting.

Use file-level and row-level deduplication.

File-level:

```text
file_hash
workspace_id
account_id
```

Row-level dedupe hash may include:

```text
workspace_id
account_id
operation_date
amount
description_normalized
balance_after optional
bank_operation_id optional
```

Rules:

```text
Duplicate rows should be visible in review.
Duplicates must not be posted twice.
Repeated imports of the same file must be safe.
Overlapping statement periods must require review.
```

Acceptance criteria:

```text
1. Same PDF upload is detected.
2. Same raw row is detected.
3. Duplicate status appears in review screen.
4. Duplicate rows cannot silently create new operations.
```

---

### Phase 14 — Minimal categories and optional property link

Goal: make imported financial data more useful without building a full categorization system.

Implement:

```text
basic category seed per workspace
category_id nullable on Operation
property_id nullable on Operation
minimal Property model optional
```

Use cases:

```text
Rent payment -> category Rent -> property 9 Maya 20
Repair expense -> category Repair -> property 9 Maya 20
Groceries -> category Expense or Uncategorized
Bank fee -> category Bank fee
```

Rules:

```text
Categories are classification, not ownership boundaries.
Workspace is the ownership and access boundary.
Property is optional and should only affect property-related reports.
```

Acceptance criteria:

```text
1. Confirmed operations can have a category.
2. Confirmed operations can optionally link to a property.
3. Basic report by category is possible.
4. Basic report by property is possible if Property is implemented.
```

---

### Phase 15 — Minimal reports

Goal: show that imported data becomes useful.

Implement only simple reports:

```text
Account balance
Income total for period
Expense total for period
Net result for period
Operations list by period
Optional category totals
Optional property totals
```

Do not implement advanced dashboards yet.

Acceptance criteria:

```text
1. User can see account balance.
2. User can see confirmed operations for a period.
3. User can see basic income/expense totals.
4. Reports ignore raw unconfirmed rows.
5. Reports ignore internal transfers when calculating profit.
```

---

## 9. MVP user stories

### Story 1 — Upload a statement

```text
As a financially aware user,
I want to upload a PDF bank statement,
so that Booker Tee can extract transactions from it.
```

Acceptance criteria:

```text
Given I am in a workspace
When I upload a supported PDF
Then the document is saved
And a parse attempt is created
And I can open the document detail page
```

---

### Story 2 — Inspect raw extraction

```text
As a user,
I want to see what Booker Tee extracted from my PDF,
so that I can trust the parser before posting transactions.
```

Acceptance criteria:

```text
Given a parsed document
When I open the document detail page
Then I see raw extracted rows
And I see parser status
And I see rows that need review
```

---

### Story 3 — Validate statement totals

```text
As a user,
I want Booker Tee to compare extracted rows with statement totals,
so that missing or duplicated rows do not corrupt my financial data.
```

Acceptance criteria:

```text
Given a statement with control totals
When parsing finishes
Then Booker Tee compares calculated totals with statement totals
And mismatches are shown as requires_review
And mismatched statements are not silently posted
```

---

### Story 4 — Confirm rows into ledger

```text
As a user,
I want to confirm parsed rows,
so that they become real financial operations and affect account balances.
```

Acceptance criteria:

```text
Given valid raw rows
When I confirm them
Then Booker Tee creates Operation records
And MoneyEntry records
And links RawTransaction to Operation
And updates calculated account balance
```

---

### Story 5 — Avoid duplicate imports

```text
As a user,
I want Booker Tee to detect duplicate uploads and duplicate rows,
so that my income, expenses, and balances are not counted twice.
```

Acceptance criteria:

```text
Given I already imported a statement
When I upload it again
Then Booker Tee detects the duplicate
And does not create duplicate ledger entries
```

---

### Story 6 — Handle cash-to-card-to-deposit correctly

```text
As a landlord,
I want Booker Tee to distinguish rent income from internal transfers,
so that my property income is not counted multiple times.
```

Correct interpretation:

```text
Received cash rent for 9 Maya 20 -> income, affects_profit=true
Deposited cash to card -> transfer, affects_profit=false
Moved card money to deposit -> transfer, affects_profit=false
```

Acceptance criteria:

```text
Given a rent income and later internal transfers
When reports are calculated
Then rent is counted as income once
And internal transfers affect account balances only
And internal transfers do not affect profit or property ROI
```

---

## 10. Core screens for the MVP

### 10.1 Accounts list

Purpose:

```text
Create/select accounts where imported rows will be posted.
```

Minimum content:

```text
Account name
Account type
Currency
Bank/card hint
Calculated balance
Create account action
```

---

### 10.2 Upload document page

Purpose:

```text
Upload PDF bank statement and assign it to an account/workspace.
```

Minimum content:

```text
Selected workspace
Selected account
PDF file input
Upload button
Recent uploaded documents
```

---

### 10.3 Uploaded documents list

Purpose:

```text
Track parsing status and open review.
```

Minimum content:

```text
Filename
Account
Status
Parser name
Rows found
Validation status
Uploaded at
Actions: view, reparse
```

---

### 10.4 Document review page

Purpose:

```text
Review extracted rows and confirm them into the ledger.
```

Minimum content:

```text
Document metadata
Parser attempt summary
Control totals
Validation status
RawTransaction table
Confirm/ignore actions
Confirm all valid rows action
```

---

### 10.5 Operations list

Purpose:

```text
Show confirmed ledger records.
```

Minimum content:

```text
Date
Type
Description
Amount
Account
Category optional
Property optional
Source document optional
```

---

### 10.6 Basic report page

Purpose:

```text
Show that imported data became useful.
```

Minimum content:

```text
Period selector
Total income
Total expenses
Net result
Account balances
Optional category totals
Optional property totals
```

---

## 11. Suggested endpoints

Exact routes may change, but the MVP should contain these capabilities.

```text
GET  /health
GET  /accounts
POST /accounts
GET  /documents
GET  /documents/upload
POST /documents/upload
GET  /documents/{document_id}
POST /documents/{document_id}/parse
POST /documents/{document_id}/reparse
POST /raw-transactions/{raw_transaction_id}/confirm
POST /raw-transactions/{raw_transaction_id}/ignore
POST /documents/{document_id}/confirm-valid
GET  /operations
GET  /reports/summary
```

If using HTMX, form posts may return partial templates instead of JSON.

---

## 12. Service boundaries

Recommended services:

```text
WorkspaceService
AccountService
DocumentService
ParserService
RawTransactionService
ImportReviewService
LedgerPostingService
BalanceService
ReportService
```

Critical rules:

```text
ParserService creates raw data only.
LedgerPostingService creates Operation + MoneyEntry.
ReportService reads confirmed ledger records only.
BalanceService calculates balances from MoneyEntry.
DocumentService never deletes original files after parser failure.
```

---

## 13. Parser architecture

Use a pluggable parser architecture.

Recommended structure:

```text
src/app/features/imports/
  parsers/
    base.py
    registry.py
    common.py
    tbank.py
    configs/
      tbank.yaml
```

Parser base contract:

```python
class StatementParser:
    parser_name: str
    parser_version: str

    def can_parse(self, file_path: str) -> bool:
        ...

    def extract(self, file_path: str) -> ParserExtractionResult:
        ...

    def normalize(self, extraction: ParserExtractionResult) -> NormalizationResult:
        ...

    def validate(self, result: NormalizationResult) -> ValidationResult:
        ...
```

Parser output should include:

```text
statement metadata
raw tables
raw rows
normalized drafts
validation result
warnings
errors
```

Rules:

```text
Parser code must be isolated per bank/statement type.
Parser output must be deterministic for the same fixture.
Parser must preserve raw payloads.
Parser must fail gracefully.
Parser must never directly post confirmed ledger operations.
```

---

## 14. Data integrity rules

### 14.1 Money

```text
Use Decimal in Python.
Use Numeric in PostgreSQL.
Never use float.
Store currency explicitly.
```

### 14.2 Workspace isolation

```text
Every workspace-owned query must filter by workspace_id.
Background jobs must receive workspace_id explicitly.
Imports must not read or write across workspaces.
```

### 14.3 Raw data preservation

```text
Original PDF must be preserved.
Extracted raw tables must be preserved.
Raw rows must be preserved.
Normalized values must not replace raw strings.
```

### 14.4 Review before posting

```text
RawTransaction is not a ledger record.
Operation + MoneyEntry are ledger records.
Only confirmed rows affect balances and reports.
```

### 14.5 Transfers

```text
Internal transfers never count as income, expense, profit, or property ROI.
Internal transfers only change where money is stored.
```

### 14.6 Validation

```text
Control-total mismatch requires review.
Parser uncertainty requires review.
Duplicate rows require review or duplicate status.
Failed parse attempts must not mutate confirmed ledger records.
```

---

## 15. Testing strategy

### 15.1 Unit tests

Test:

```text
money parsing
Russian amount formats
date parsing
description normalization
dedupe hash generation
statement total validation
transfer posting rules
balance calculation
workspace scoping helpers
```

### 15.2 Parser fixture tests

Use real or sanitized PDF fixtures.

For every supported fixture, assert:

```text
parser can identify the file
expected number of rows extracted
known row values match expected output
inflow/outflow totals match expected values
validation status is correct
no confirmed Operation is created during parsing
```

### 15.3 Integration tests

Test the full import flow:

```text
upload PDF
create UploadedDocument
create ParseAttempt
create RawTransaction rows
show review data
confirm raw rows
create Operation + MoneyEntry
calculate account balance
repeat upload does not double count
```

### 15.4 Regression tests

Every time a bank parser bug is fixed, add a fixture or sample row test to prevent regression.

---

## 16. MVP acceptance checklist

The first MVP is done only when all of these are true:

```text
[ ] App runs locally with PostgreSQL.
[ ] Alembic migrations create all MVP tables.
[ ] A personal workspace exists for the user.
[ ] Account can be created and selected.
[ ] PDF can be uploaded and stored.
[ ] UploadedDocument stores file metadata and hash.
[ ] ParseAttempt is created for parser run.
[ ] pdfplumber extraction stores raw tables JSON.
[ ] First bank parser extracts rows from 2-3 fixtures.
[ ] RawTransaction rows are created.
[ ] Dates, amounts, descriptions, and currency are normalized.
[ ] Statement totals are validated when available.
[ ] Review screen displays document status and rows.
[ ] User can confirm valid rows.
[ ] Confirmed rows create Operation + MoneyEntry.
[ ] Account balance is calculated from MoneyEntry.
[ ] Duplicate file upload is detected.
[ ] Duplicate raw rows are not posted twice.
[ ] Parser failure does not delete source files.
[ ] Tests cover parser and ledger posting.
[ ] Reports use confirmed ledger data only.
[ ] Internal transfers do not affect profit.
```

---

## 17. Recommended Codex task sequence

Use small vertical tasks. Do not ask Codex to implement the whole MVP at once.

### Task 1 — Project foundation

```text
Create FastAPI project skeleton with config, async SQLAlchemy, PostgreSQL session, Alembic, pytest, healthcheck, and base templates. Follow AGENTS.md.
```

### Task 2 — Workspace foundation

```text
Implement User, Workspace, WorkspaceMember models, migrations, repositories, and a simple automatic personal workspace creation flow. Ensure all workspace-owned queries are scoped by workspace_id.
```

### Task 3 — Accounts

```text
Implement minimal Account model, migration, repository, service, routes, and templates for creating/listing accounts in the active workspace.
```

### Task 4 — Uploaded documents

```text
Implement UploadedDocument model, migration, PDF upload flow, file storage, file hash calculation, document status, and documents list/detail pages.
```

### Task 5 — Parse attempts and raw extraction

```text
Implement ParseAttempt model and parser service that uses pdfplumber to extract raw tables from uploaded PDFs and stores extracted_tables_json. Add reparse action.
```

### Task 6 — First bank parser

```text
Create parser interface and first parser for one bank statement type. Add sanitized PDF fixtures and tests for extraction.
```

### Task 7 — Raw transactions

```text
Implement RawTransaction model and convert parsed rows into raw transaction records while preserving raw_payload. Show rows on document detail page.
```

### Task 8 — Normalization and validation

```text
Implement normalization for dates, Decimal amounts, currency, description, inflow/outflow direction, and statement control-total validation. Mark uncertain or mismatched rows/documents as requires_review.
```

### Task 9 — Review screen

```text
Implement review UI for raw transactions with confirm, ignore, edit basic normalized fields, and confirm all valid rows.
```

### Task 10 — Ledger posting

```text
Implement Operation and MoneyEntry models, migrations, LedgerPostingService, and confirmation flow from RawTransaction to Operation + MoneyEntry. Ensure idempotency and database transaction safety.
```

### Task 11 — Balances and simple reports

```text
Implement account balance calculation from MoneyEntry and a minimal summary report for income, expenses, net result, and account balances.
```

### Task 12 — Deduplication

```text
Implement file-level and raw-row-level deduplication. Ensure repeated uploads and repeated confirmations do not double-count money.
```

### Task 13 — Minimal classification

```text
Seed basic workspace categories and optionally implement minimal Property model/linking for DIY landlord use cases.
```

---

## 18. MVP quality bar

The MVP should feel narrow but trustworthy.

It is acceptable if:

```text
only one bank is supported
UI is simple
manual review is required
categories are basic
properties are minimal or absent
reports are simple
parsing is not fully autonomous
```

It is not acceptable if:

```text
raw source data is lost
parser errors crash the app
confirmed data is created without review
money is stored as float
workspace boundaries are ignored
duplicates double-count money
internal transfers are counted as income
failed imports pollute reports
balances are manually mutated and become inconsistent
```

---

## 19. Decision filter for MVP work

Before adding a feature, ask:

```text
Does this make PDF import more reliable?
Does this make extracted data more trustworthy?
Does this help the user review and confirm rows?
Does this prevent duplicate or incorrect financial records?
Does this help convert confirmed rows into correct balances/reports?
```

If the answer is no, the feature probably belongs after the MVP.

---

## 20. Final MVP mantra

```text
Real PDF in.
Raw data preserved.
Rows normalized.
Totals validated.
User reviews.
Ledger confirmed.
Balances trusted.
No double-counting.
```
