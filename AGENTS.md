# AGENTS.md — Booker Tee

Project instructions for Codex and other coding agents.

Official references:
- Codex AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- uv: https://docs.astral.sh/uv/
- Ruff: https://docs.astral.sh/ruff/
- ty: https://docs.astral.sh/ty/

## 1. Product focus

Booker Tee is a private financial assistant focused first on reliable financial data import.

Current MVP focus:

```text
PDF bank statement -> raw extracted data -> normalized transactions -> validation -> review -> confirmed accounting
```

Do not turn the MVP into a broad AI/asset-management platform too early. The first valuable product is a trustworthy importer and review flow for bank statements, manual cash movements, accounts, categories, and property-linked income/expenses.

## 2. Core product principles

1. Reliability over magic.
2. Financial correctness over UI polish.
3. User review over silent automation.
4. Raw imported data must never be lost.
5. Internal transfers must never be counted as income or expense.
6. Workspaces are strict data boundaries.
7. Private financial data must not be sent to external AI/API services unless explicitly requested.

## 3. Tech stack

Use this stack unless the repository already contains a conflicting decision:

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0, async style
- Alembic
- Pydantic v2
- PostgreSQL
- Jinja2 templates for SSR
- HTMX for server-driven interactivity
- Alpine.js for small client-side interactions
- Tailwind CSS for styling
- pdfplumber for PDF table extraction
- Celery/Redis only when background processing is explicitly needed
- pgvector / local LLM / RAG only in later phases, not in the first MVP unless explicitly requested

## 4. Package management and quality tools

Use Astral tooling.

Package management:

```bash
uv sync
uv add <package>
uv add --dev <package>
uv run <command>
```

Do not use plain `pip install`, Poetry, Pipenv, or ad-hoc virtualenv commands unless the user explicitly asks.

Linting and formatting:

```bash
uv run ruff format .
uv run ruff check .
```

Type checking:

```bash
uv run ty check .
```

Tests:

```bash
uv run pytest
```

Before finishing a coding task, run the relevant checks. If a command cannot be run because dependencies or infrastructure are missing, explain that clearly in the final response.

## 5. Repository approach

Before changing code:

1. Inspect the existing project structure.
2. Read relevant markdown files, especially:
   - `PROJECT_VISION.md`
   - `DOMAIN_MODEL.md`
   - `ARCHITECTURE.md`
   - `MVP.md`
   - `ROADMAP.md`
   - this `AGENTS.md`
3. Respect existing decisions unless the task asks to change them.
4. Keep changes small and focused.
5. Do not rewrite unrelated files.
6. Do not introduce new frameworks without a strong reason.

When adding a feature, prefer one complete vertical slice over scattered partial code.

## 6. Architecture style

Use feature-driven vertical slices with clear layers inside each feature:

```text
Router -> Service -> Repository -> Model
```

Recommended initial layout:

```text
src/app/
  main.py
  core/
    config.py
    security.py
  db/
    base.py
    session.py
  features/
    workspaces/
      models.py
      schemas.py
      repository.py
      service.py
      router.py
    accounts/
      models.py
      schemas.py
      repository.py
      service.py
      router.py
    operations/
      models.py
      schemas.py
      repository.py
      service.py
      router.py
    categories/
      models.py
      schemas.py
      repository.py
      service.py
      router.py
    documents/
      models.py
      schemas.py
      repository.py
      service.py
      router.py
    imports/
      parsers/
      models.py
      schemas.py
      repository.py
      service.py
      router.py
  templates/
  static/
tests/
```

Layer rules:

- Routers handle HTTP, request parsing, response rendering, and dependency injection.
- Services contain business rules and use cases.
- Repositories contain database queries.
- Models define persistence only.
- Schemas define external input/output contracts.
- Templates must not contain business logic.
- Every database schema change must include an Alembic migration.

## 7. Workspace-first rule

Booker Tee must be multi-workspace by design.

A `User` is a person. A `Workspace` is a financial context such as personal budget, family, business, property management, or project.

Almost every business entity must belong to a workspace:

```text
accounts.workspace_id
categories.workspace_id
operations.workspace_id
money_entries.workspace_id or operation.workspace_id
properties.workspace_id
uploaded_documents.workspace_id
parse_attempts.workspace_id
raw_transactions.workspace_id
transaction_rules.workspace_id
```

Use `created_by_user_id`, `updated_by_user_id`, or audit fields to record who performed an action. Do not use `user_id` as the main ownership boundary for financial data.

Every query for workspace-owned data must filter by `workspace_id`.

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

## 8. Financial domain model

Use these concepts:

```text
Account       = where money is stored
Operation     = business meaning of a money event
MoneyEntry    = actual movement on one account
Category      = why money appeared/disappeared
Property      = optional object/property linked to the operation
RawTransaction = imported bank row before confirmation
```

Prefer this accounting shape:

```text
Operation 1 -> N MoneyEntry
```

Examples:

Income from rent paid in cash:

```text
Operation:
  type = income
  affects_profit = true
  category = Rent
  property = 9 Maya 20

MoneyEntry:
  account = Cash/Safe
  amount = +40000
```

Cash deposited to card:

```text
Operation:
  type = transfer
  affects_profit = false

MoneyEntry:
  account = Cash/Safe
  amount = -40000

MoneyEntry:
  account = Bank Card
  amount = +40000
```

Card transferred to deposit:

```text
Operation:
  type = transfer
  affects_profit = false

MoneyEntry:
  account = Bank Card
  amount = -40000

MoneyEntry:
  account = Deposit
  amount = +40000
```

Critical rule:

```text
Income/expense changes financial result.
Transfer changes only the location of money.
```

Never count internal transfers as income, expense, profit, or property ROI.

## 9. Money and precision

- Use `Decimal` in Python.
- Use PostgreSQL `Numeric(12, 2)` or stricter precision for money.
- Never use `float` for money.
- Store currency explicitly.
- Store `operation_date`.
- Store `posting_date` / `processed_at` when imported from banks and available.

## 10. Operation statuses

Imported or manually created operations should support review states:

```text
draft
needs_review
confirmed
ignored
duplicate
```

Do not silently publish questionable imported data into confirmed accounting.

## 11. PDF import pipeline

PDF import must be robust and reviewable.

Use this pipeline:

```text
uploaded_documents
  -> parse_attempts
  -> raw_transactions
  -> normalized draft operations/money_entries
  -> validation
  -> review
  -> confirmed operations/money_entries
```

Rules:

1. Store the uploaded document metadata and file reference first.
2. Extract raw text/tables and keep them for debugging.
3. Save each parser run as a `parse_attempt`.
4. Save extracted rows as `raw_transactions`.
5. Do not create confirmed operations directly from a PDF parser.
6. If parsing fails, set the document/attempt status to `failed_to_parse` and preserve raw data.
7. If validation is uncertain, set status to `requires_review` / `needs_review`.
8. Add idempotency/deduplication so the same statement can be uploaded twice safely.

## 12. Parser design

Use parser classes per bank and statement type.

Recommended shape:

```text
BaseStatementParser
TBankCardStatementParser
TBankDepositStatementParser
SberCardStatementParser
AlfaCardStatementParser
```

Use a parser factory to detect the correct parser by document markers.

Prefer configuration over hardcoded column positions:

```text
parsers/configs/tbank_card.yaml
parsers/configs/tbank_deposit.yaml
```

Parser configs may define:

```yaml
bank_name: "T-Bank"
statement_type: "card"
markers:
  - "T-BANK"
header_keywords:
  - "Дата операции"
  - "Сумма"
  - "Описание"
mapping:
  operation_date_col: 0
  description_col: 1
  amount_col: 3
date_format: "%d.%m.%Y"
```

Use `pdfplumber` table extraction first. Avoid OCR unless there is no other option.

## 13. Statement validation

When the bank statement contains control totals, parse and verify them:

```text
opening_balance
income_total
expense_total
closing_balance
```

Expected formula:

```text
opening_balance + income_total - expense_total = closing_balance
```

If the formula does not match, do not confirm imported operations automatically. Mark the import as requiring review.

## 14. Deduplication

Bank imports must be idempotent.

Use a deterministic deduplication hash where possible:

```text
workspace_id
account_id
operation_date
posting_date if available
amount
currency
normalized_description
balance_after if available
source_document_id or statement period when useful
```

If confidence is high, mark as duplicate automatically. If confidence is medium, mark as possible duplicate and ask for review.

## 15. Categories and rules

Categories are workspace-specific.

Support system categories that cannot be deleted casually:

```text
Transfer
Adjustment
Refund
Duplicate
Ignore / Do not count
Uncategorized
```

Transaction rules are also workspace-specific. A rule may match normalized description, counterparty, amount pattern, account, or recurrence and then suggest:

```text
category_id
property_id
auto_description
operation_type
```

Rules should suggest or prefill. For risky cases, keep user review.

## 16. Property management MVP

For the MVP, keep property management small.

Required early model:

```text
Property
- id
- workspace_id
- name
- short_name
- address optional
- status optional
```

Transactions/operations may be linked to a property with `property_id`.

Do not implement meters, vacancy rate, tenants, lease documents, deposits, and complex ROI unless the task explicitly asks.

Important tenant deposit rule:

```text
Tenant security deposits are not income until retained.
```

## 17. Security and privacy

This project handles sensitive financial data.

- Never commit real bank statements, passports, contracts, `.env` files, tokens, passwords, or secrets.
- Use sanitized fixtures for tests.
- Do not log full PDF text, full card numbers, account numbers, personal names, or sensitive descriptions.
- Mask sensitive values in logs and error messages.
- Prefer local processing for PDFs.
- Do not send user financial data to external AI services unless explicitly requested.
- Add authorization checks before data access.

## 18. UI rules

Use a dark techno-neobrutalist style with Catppuccin Mocha-inspired colors.

Design rules:

- No rounded corners: `border-radius: 0`.
- Prefer clear borders over soft shadows.
- Mobile-first layout.
- Touch targets at least 44x44px.
- Use monospaced font for amounts, dates, IDs, statuses, and financial tables.
- Use sans-serif font for normal text.
- Keep financial tables readable before making them decorative.

## 19. Testing expectations

Add tests for business-critical behavior.

Prioritize tests for:

- Internal transfer does not affect profit.
- Income/expense affects profit correctly.
- Workspace isolation: users cannot access other workspace data.
- PDF parser preserves raw rows.
- Failed parser attempts do not delete uploaded documents.
- Control-total mismatch creates `needs_review` / `requires_review`.
- Deduplication detects repeated imports.
- Category rules apply only inside the current workspace.

## 20. Database and migrations

- Use Alembic for every schema change.
- Keep migrations deterministic.
- Avoid destructive migrations unless explicitly requested.
- Use indexes for common workspace-scoped queries.
- Add foreign keys for ownership and integrity.
- Prefer explicit enum values and stable names.

Recommended indexes:

```text
(workspace_id, operation_date)
(workspace_id, account_id)
(workspace_id, category_id)
(workspace_id, property_id)
(workspace_id, status)
(workspace_id, dedupe_hash)
```

## 21. What not to build yet

Do not implement these unless explicitly requested:

- RAG
- Text-to-SQL
- local LLM assistant
- Telegram bot
- IMAP ingestion
- complex RBAC UI
- full property management
- tenant management
- utility meters
- vacancy metrics
- complex dashboards
- paid SaaS billing

Keep the MVP narrow.

## 22. Final response format for coding tasks

When finishing a task, report:

1. What changed.
2. Files changed.
3. Commands run.
4. Test/lint/type-check result.
5. Any known limitations or follow-up needed.

Do not claim checks passed if they were not run.
