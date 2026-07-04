# DOMAIN_MODEL.md - Booker Tee

Canonical domain model for Booker Tee.

Status: active source of truth.

Read when changing models, migrations, repositories, services, imports, ledger
posting, reports, deduplication, workspace access, or financial invariants.

Do not use as a UI implementation plan or sprint checklist. For UI/SSR work read
[`DESIGN.md`](../design/DESIGN.md) and
[`REFACTOR_PROJECT_DESIGN.md`](../design/REFACTOR_PROJECT_DESIGN.md). For
sequencing read [`ROADMAP.md`](../product/ROADMAP.md).

Current assessment: the original MVP is complete and exceeded. This file is now
a compact domain reference, not the historical MVP implementation plan.

---

## 1. Domain Summary

Booker Tee turns manual cash operations and imported bank statements into
reliable, reviewable, confirmed financial records.

Core flow:

```text
PDF bank statement / manual entry
  -> raw extracted data
  -> normalized draft rows
  -> validation and deduplication
  -> user review
  -> confirmed operations and account movements
```

The model must prevent the most dangerous financial error: counting the same
money movement as income several times.

Example:

```text
1. Received cash rent for property "9 Maya 20" -> income, affects profit
2. Deposited this cash to a bank card          -> transfer, does not affect profit
3. Moved money from card to deposit            -> transfer, does not affect profit
```

Only the first event is income. The second and third events only change where
the same money is stored.

---

## 2. Core Concepts

| Concept | Meaning |
| --- | --- |
| `User` | Human identity that can log in. |
| `UserSession` | Authenticated session and current workspace convenience state. |
| `Workspace` | Strict financial data boundary. |
| `WorkspaceMember` | User role inside a workspace. |
| `WorkspaceInvitation` | Workspace invite with token hash and lifecycle. |
| `WorkspaceAuditEvent` | Audit event for workspace/member/invitation changes. |
| `Account` | Where money is stored: cash, card, deposit, checking account. |
| `Category` | Why money appeared or disappeared. |
| `Property` | Optional real estate object for analytics. |
| `Operation` | Business meaning of a money event. |
| `MoneyEntry` | Signed movement on one concrete account. |
| `UploadedDocument` | Uploaded source document metadata. |
| `ParseAttempt` | One parser run against one document. |
| `RawTransaction` | Extracted/imported row before confirmed posting. |
| `ImportMappingTemplate` | Reusable column mapping for unknown statements. |
| `TransactionRule` | Workspace-specific suggestion/autofill rule. |
| `IntegrationConnection` | Chat/integration connection scoped to workspace. |

Recommended accounting shape:

```text
Operation 1 -> N MoneyEntry
```

Do not model confirmed events as one flat `Transaction(amount, account_id)` row.
Internal transfers need at least two entries: negative on the source account and
positive on the destination account.

---

## 3. Relationship Overview

```text
User -> UserSession
User -> WorkspaceMember -> Workspace
User -> WorkspaceInvitation / WorkspaceAuditEvent actor fields

Workspace -> Account
Workspace -> Category
Workspace -> Property
Workspace -> Operation -> MoneyEntry -> Account
Workspace -> UploadedDocument -> ParseAttempt -> RawTransaction
Workspace -> ImportMappingTemplate
Workspace -> TransactionRule
Workspace -> IntegrationConnection / Chat bindings / Chat state / Deliveries

RawTransaction -> linked Operation after review/confirmation
Operation -> optional Category
Operation -> optional Property
Category -> optional parent Category
```

---

## 4. Workspace-First Rule

A `Workspace` is the main ownership boundary for financial data. A `User` is not.

Workspace-owned data includes accounts, categories, properties, operations,
money entries, uploaded documents, parse attempts, raw transactions, import
mapping templates, transaction rules, workspace members/invitations/audit events,
and integration state.

Use actor fields such as `created_by_user_id`, `updated_by_user_id`, and
`uploaded_by_user_id` to record who did something.

Every query for workspace-owned data must be scoped by `workspace_id`.

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

This applies to reads, updates, deletes, imports, exports, reports, HTMX partial
updates, background jobs, and integration handlers.

---

## 5. Current Entity Reference

Exact SQLAlchemy fields live in `src/app/features/*/models.py`. This section
documents domain meaning, key fields, and rules.

| Entity | Key Fields | Rules |
| --- | --- | --- |
| `User` | `id`, `email`, `password_hash`, `name`, `is_active` | Email is normalized. Financial data should not be owned directly by `user_id`. |
| `UserSession` | `user_id`, `current_workspace_id`, `session_token_hash`, `expires_at`, `revoked_at` | Store token hashes, not raw tokens. Current workspace does not bypass membership checks. |
| `Workspace` | `owner_id`, `name`, `slug`, `type`, `default_currency`, `archived_at` | Owner must also be a member. Reports are workspace-scoped. |
| `WorkspaceMember` | `workspace_id`, `user_id`, `role`, `status`, `invited_by_user_id` | `unique(workspace_id, user_id)`. Disabled/removed members must not access workspace data. |
| `WorkspaceInvitation` | `workspace_id`, `role`, `status`, `token_hash`, `expires_at`, `accepted_at`, `revoked_at` | Store token hashes. Accepting an invite creates/updates membership in the same workspace. |
| `WorkspaceAuditEvent` | `workspace_id`, `event_type`, `actor_user_id`, `target_user_id`, `entity_type`, `entity_id`, `details` | Workspace-scoped. Do not log sensitive document contents. |
| `Account` | `workspace_id`, `name`, `type`, `currency`, `initial_balance`, `is_active`, `bank_name`, `card_last4`, `archived_at` | Balance is derived from confirmed `MoneyEntry` records. Never store full card/account numbers. |
| `Category` | `workspace_id`, `parent_id`, `name`, `kind`, `is_active`, `is_system`, `system_key` | Workspace-specific. Trees must not cycle. System categories are protected. |
| `Property` | `workspace_id`, `name`, `short_name`, `address`, `status`, `archived_at` | Financial-first property analytics. Not a full property CRM. |
| `Operation` | `workspace_id`, `type`, `status`, `affects_profit`, `category_id`, `property_id`, `operation_date`, `source` | Business meaning of a money event. Only confirmed operations affect official balances/reports. |
| `MoneyEntry` | `workspace_id`, `operation_id`, `account_id`, `amount`, `currency`, `entry_order`, `balance_after` | Signed movement on one account. Must match operation/account workspace. |
| `UploadedDocument` | `workspace_id`, `source`, `document_type`, `status`, `storage_key`, `sha256_hash`, `account_id` | Store metadata before parsing. Failed parsing must not delete files. |
| `ParseAttempt` | `workspace_id`, `uploaded_document_id`, `parser_name`, `status`, `raw_text_by_page_json`, `raw_tables_json`, `control_totals_json`, `validation_report_json` | Parser failures are stored. Raw extracted data is preserved. |
| `RawTransaction` | `workspace_id`, `uploaded_document_id`, `parse_attempt_id`, `row_index`, `status`, raw fields, normalized fields, suggestions, `linked_operation_id`, `normalization_error` | Raw rows do not affect balances/profit. They link to operations only after review/confirmation. |
| `ImportMappingTemplate` | `workspace_id`, `name`, `bank_name`, `statement_type`, `default_currency`, `column_mapping_json` | Helps parse unknown statements. Does not prove data is correct. |
| `TransactionRule` | `workspace_id`, `name`, `priority`, `match_type`, `pattern`, `application_mode`, match filters, suggested output fields | Rules suggest/prefill. They must not bypass review or financial invariants. |
| `IntegrationConnection` and chat state | `workspace_id`, provider/binding/state/delivery fields | Integration actions must obey the same workspace and review rules as web actions. |

---

## 6. Enum Reference

Keep enum values stable. Changing them usually requires migrations and data
cleanup.

| Enum | Values |
| --- | --- |
| `WorkspaceType` | `personal`, `family`, `business`, `property_management`, `project`, `other` |
| `WorkspaceRole` | `owner`, `admin`, `editor`, `viewer`, `uploader`, `analyst` |
| `WorkspaceMemberStatus` | `pending`, `active`, `disabled`, `removed` |
| `WorkspaceInvitationStatus` | `pending`, `accepted`, `revoked`, `expired` |
| `WorkspaceAuditEventType` | `workspace_created`, `workspace_updated`, `invitation_created`, `invitation_accepted`, `invitation_revoked`, `member_role_changed`, `member_disabled`, `member_reactivated` |
| `AccountType` | `cash`, `card`, `deposit`, `checking`, `other` |
| `CategoryKind` | `income`, `expense`, `transfer`, `adjustment`, `mixed` |
| `PropertyStatus` | `active`, `inactive`, `archived` |
| `OperationType` | `income`, `expense`, `transfer`, `adjustment` |
| `OperationStatus` | `draft`, `needs_review`, `confirmed`, `ignored`, `duplicate` |
| `OperationSource` | `manual`, `bank_pdf`, `system` |
| `UploadedDocumentSource` | `web_upload`, `system` |
| `UploadedDocumentType` | `bank_statement`, `other` |
| `UploadedDocumentStatus` | `uploaded`, `pending_parse`, `parsing`, `parsed`, `requires_review`, `failed_to_parse`, `imported`, `ignored` |
| `ParseAttemptStatus` | `running`, `success`, `requires_review`, `failed` |
| `RawTransactionStatus` | `extracted`, `normalized`, `suggested`, `needs_review`, `matched`, `ignored`, `duplicate`, `possible_duplicate`, `failed`, `confirmed` |
| `TransactionRuleMatchType` | `contains`, `exact` |
| `MoneyDirection` | `inflow`, `outflow`, `any` |
| `TransactionRuleApplicationMode` | `suggest`, `auto_apply` |
| `ChatProviderCode` | `fake`, `matrix`, `telegram` |
| `IntegrationConnectionStatus` | `active`, `disabled` |
| `ChatConversationBindingMode` | `personal_input`, `review`, `shared_feed` |
| `ChatNotificationLevel` | `none`, `safe_activity`, `review_alerts` |
| `ChatConversationFlow` | `main_menu`, `link_account`, `upload_document`, `review`, `record_expense`, `record_income`, `record_transfer` |
| `IntegrationDeliveryStatus` | `pending`, `sent`, `failed` |

---

## 7. Financial Rules

### Account Balance

Canonical balance:

```text
account.initial_balance
+ sum(money_entries.amount)
  where operation.status = "confirmed"
  and money_entries.account_id = account.id
```

Draft, review, ignored, and duplicate operations do not change official balance.

### Operation Rules

| Type | Entries | `affects_profit` | Meaning |
| --- | ---: | ---: | --- |
| `income` | usually 1 positive entry | true by default | Money appeared because the user earned/received income. |
| `expense` | usually 1 negative entry | true by default | Money disappeared because the user spent money. |
| `transfer` | exactly 2 entries in current same-currency flow | always false | Money moved between own accounts. |
| `adjustment` | usually 1 entry | usually false | Opening balance, correction, or non-profit movement. |

Rules:

- Transfers must not affect profit or property ROI.
- Same-currency transfer entries must sum to zero.
- Income and expense should affect profit unless explicitly marked otherwise for
  a valid reason.
- Confirmed operations should be corrected carefully, not casually hard-deleted.

### Money Entry Rules

- Use signed amounts.
- `money_entries.workspace_id` must match both operation and account workspace.
- Never use `float` for money.
- Use `Decimal` in Python and `Numeric(14, 2)` or stricter in PostgreSQL.

### Category Rules

- Categories are workspace-specific.
- Category trees must not form cycles.
- System categories can be hidden/archived only carefully.
- Current review UX treats income/expense without category as not safely
  confirmable by default.

### Property Rules

Property profit/loss uses only:

```text
operation.status = "confirmed"
operation.affects_profit = true
operation.property_id = target_property_id
```

Internal transfers must not affect property ROI.

### Raw Transaction Rules

- Raw transactions do not directly affect balances or profit.
- Many raw rows may link to one operation, especially for transfers.
- `ready_to_confirm` is presentation-only, not a backend status.
- `possible_duplicate` means the user should review a likely match.
- `confirmed` means the raw row has been processed into or linked to confirmed
  accounting.

### Tenant Security Deposit Rule

A tenant security deposit is money held by the user but not earned yet.

Current representation:

```text
Operation.type = "adjustment"
Operation.affects_profit = false
Category = "Tenant deposit" / "Security deposit"
MoneyEntry.amount = positive amount on receiving account
Property = target property if useful
```

Do not count tenant deposits as income until retained for a valid reason.

---

## 8. Import Pipeline

Bank statement import must stay reviewable:

```text
1. User uploads source document in active workspace.
2. Create UploadedDocument.
3. Create ParseAttempt.
4. Extract raw text/tables.
5. Detect parser or use unknown-statement mapping.
6. Save RawTransaction rows.
7. Normalize date, amount, currency, description, account hints.
8. Calculate dedupe hashes.
9. Validate control totals when available.
10. Apply transaction rules as structured suggestions.
11. Show review queue.
12. User confirms, ignores, marks duplicate, or resolves transfer/category.
13. Create/link confirmed Operation + MoneyEntry records.
14. Link RawTransaction rows to confirmed Operation records.
```

Parser rule:

```text
PDF parser -> RawTransaction -> review -> confirmed Operation
```

Never:

```text
PDF parser -> confirmed Operation
```

### Statement Validation

When available, parse:

```text
opening_balance
income_total / total_inflow
expense_total / total_outflow
closing_balance
```

Expected formula:

```text
opening_balance + income_total - expense_total = closing_balance
```

If totals mismatch, mark the document/attempt/rows as requiring review. Do not
publish confirmed operations automatically.

### Deduplication

Imports must be idempotent.

Suggested exact dedupe input:

```text
workspace_id
account_id
operation_date
posting_date if available
amount
currency
normalized_description
balance_after if available
document hash or statement period when useful
```

Possible duplicate fingerprint may use:

```text
workspace_id
account_id
operation_date
amount
currency
```

Exact duplicate -> mark duplicate or avoid creating another operation.
Possible duplicate -> show review hint. Same PDF or overlapping statement
periods must not double-count income or expenses.

---

## 9. Business Scenarios

### Rent Received In Cash, Then Deposited To Card

Correct:

```text
Operation 1:
  type = income
  affects_profit = true
  category = Rent
  property = 9 Maya 20
  entry: Cash +40000 RUB

Operation 2:
  type = transfer
  affects_profit = false
  entries:
    Cash -40000 RUB
    Bank Card +40000 RUB
```

Reports:

```text
Property income: +40000 RUB
Total profit: +40000 RUB
Transfer: not extra income
```

Wrong:

```text
Rent income +40000
Cash deposit +40000
Total income +80000
```

### Imported Cash Deposit Row

Bank row:

```text
+40000 RUB "Cash deposit via ATM"
```

It can be new income, transfer from cash, balance adjustment, or refund. Default
behavior: require review or suggest transfer if enough context exists. Do not
automatically count this as income.

### Transfer Between Two Imported Bank Accounts

Expected result:

```text
One Operation(type="transfer", affects_profit=false)
Two MoneyEntry rows
Two RawTransaction rows linked to the same Operation
```

### Property Expense

```text
Operation.type = "expense"
Operation.affects_profit = true
Category = Repair
Property = 9 Maya 20
MoneyEntry = Bank Card -8500 RUB
```

This reduces profit for property `9 Maya 20`.

---

## 10. Reporting Rules

Account balance:

```text
initial_balance + confirmed money entries for account
```

Workspace profit/loss:

```text
sum(money_entries.amount)
where operation.workspace_id = current_workspace_id
and operation.status = "confirmed"
and operation.affects_profit = true
```

Property profit/loss:

```text
sum(money_entries.amount)
where operation.workspace_id = current_workspace_id
and operation.status = "confirmed"
and operation.affects_profit = true
and operation.property_id = target_property_id
```

Category report:

```text
sum(money_entries.amount)
group by operation.category_id
where operation.status = "confirmed"
and operation.affects_profit = true
```

Transfer report:

```text
show operations where operation.type = "transfer"
do not include transfers in income, expense, profit, or ROI totals
```

Review queue:

```text
RawTransaction.status in (
  "extracted",
  "normalized",
  "suggested",
  "needs_review",
  "matched",
  "possible_duplicate"
)
Operation.status in ("draft", "needs_review")
UploadedDocument.status in ("requires_review", "failed_to_parse")
```

---

## 11. Deletion And Correction

Financial records are audit-sensitive.

Current rule:

```text
Draft records may be deleted.
Confirmed records should not be hard-deleted casually.
Prefer status changes, correction operations, or archive fields.
```

Future versions may add full financial audit logs, reversal operations, and
who/when/what history for financial entities.

---

## 12. Index And Constraint Guidance

Important indexes/constraints:

```text
users.email unique
user_sessions.session_token_hash unique
workspace_members(workspace_id, user_id) unique
workspace_invitations.token_hash unique
accounts(workspace_id, type)
accounts(workspace_id, is_active)
categories(workspace_id, kind)
categories(workspace_id, system_key) unique
properties(workspace_id, status)
operations(workspace_id, operation_date)
operations(workspace_id, status)
operations(workspace_id, category_id)
operations(workspace_id, property_id)
money_entries(workspace_id, account_id)
money_entries(workspace_id, operation_id)
uploaded_documents(workspace_id, status)
uploaded_documents(workspace_id, sha256_hash)
parse_attempts(workspace_id, uploaded_document_id)
raw_transactions(workspace_id, uploaded_document_id)
raw_transactions(workspace_id, parse_attempt_id)
raw_transactions(workspace_id, status)
raw_transactions(workspace_id, dedupe_hash)
transaction_rules(workspace_id, is_active, priority)
import_mapping_templates(workspace_id, bank_name, statement_type)
chat bindings unique by provider/external chat
integration deliveries unique by workspace/connection/idempotency_key
```

---

## 13. Future Entities

These are not part of the current core financial model, but current decisions
should not block them.

| Future Entity | Purpose |
| --- | --- |
| `Counterparty` | Tenants, contractors, banks, family members, business partners. |
| `RecurringOperation` | Rent, subscriptions, mortgage, taxes, regular expenses. |
| `Liability` | Loans, tenant deposits, unpaid invoices, debts. |
| `VirtualEnvelope` | Mental budgeting inside one physical account. |
| `GenericDocument` | Contracts, acts, insurance, certificates, property files. |
| Full financial `AuditLog` | Detailed who/when/what change history for financial entities. |

Do not introduce these until there is a concrete product need and a complete
vertical slice.

---

## 14. Terms To Avoid

Avoid public-facing wording that implies illegal or suspicious accounting.

Do not use:

```text
серый учет
неофициальная бухгалтерия
скрытые доходы
```

Prefer:

```text
private financial tracking
management accounting
cash-flow visibility
multi-source financial data
personal and business finance organization
```

In Russian UI or docs, prefer:

```text
личный и управленческий учет
приватный финансовый архив
учет денег из разных источников
структурирование финансовых данных
```

---

## 15. Non-Negotiable Invariants

These rules must not be broken:

1. Workspaces are strict data boundaries.
2. Every workspace-owned query must filter by `workspace_id`.
3. Money uses `Decimal` / `Numeric`, never `float`.
4. Internal transfers never count as income, expense, profit, or property ROI.
5. Raw imported data must be preserved.
6. Parsers must not create confirmed operations directly.
7. Failed parsing must not delete documents.
8. Control-total mismatch must require review.
9. Duplicate imports must not double-count money.
10. Tenant security deposits are not income until retained.
11. Draft/review/ignored/duplicate operations do not affect official balances.
12. Confirmed financial records should be corrected carefully, not casually
    hard-deleted.
13. Rules may prefill/suggest, but must not bypass financial invariants.
14. Chat/integration actions must obey the same workspace and review rules as
    web actions.
15. UI presentation states such as `ready_to_confirm` must not be confused with
    backend financial statuses unless a deliberate domain migration is made.
