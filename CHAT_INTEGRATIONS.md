# CHAT_INTEGRATIONS.md - Booker Tee

Product and engineering plan for chat-based Booker Tee integrations.

This document captures the agreed direction for Telegram and other messenger
integrations. It should be read together with:

- `PROJECT_VISION.md` - product positioning and target users;
- `DOMAIN_MODEL.md` - financial entities and invariants;
- `ARCHITECTURE.md` - code structure and layer boundaries;
- `ROADMAP.md` - phase order and product guardrails;
- `AGENTS.md` - engineering and privacy rules.

---

## 1. Product thesis

Booker Tee users may be financially responsible without being technically
confident. Many of them already know how to use messengers every day.

The chat integration should make Booker Tee easier to use by turning the
messenger into a simple financial input and review surface.

Use the principle:

```text
The user taps buttons.
Booker Tee protects correctness.
Complex cases go to review.
```

The integration must not become a broad AI chatbot or an uncontrolled financial
mutation channel. It is a guided, review-first interface for common financial
tasks.

---

## 2. Product goals

The integration should:

```text
1. Increase daily usage and data completeness.
2. Reduce forgotten cash and manual operations.
3. Make review work easier and more frequent.
4. Let users upload statements and documents from familiar apps.
5. Notify users when imports, duplicates, or review items need attention.
6. Support team/family/property workflows through shared chat notifications.
7. Keep the core Booker Tee ledger reliable and workspace-scoped.
```

The integration should not:

```text
1. Require users to learn command syntax.
2. Ask users to type technical or accounting terms.
3. Silently confirm uncertain financial records.
4. Leak private balances or sensitive descriptions into group chats by default.
5. Duplicate the parser, review, ledger, category, property, or reporting logic.
6. Couple Booker Tee directly to Telegram-specific concepts.
```

---

## 3. Naming and scope

Do not model this as only a Telegram bot.

Model it as:

```text
Chat Integrations
```

Telegram is the first provider. Other providers may be added later:

```text
Telegram
WhatsApp Business
Slack
Discord
Mattermost
VK Messenger
Email-like inbound channels
```

The core feature must use provider-neutral names:

```text
ChatProvider
ChatConversation
ChatUser
ChatMessage
ChatAction
ChatButton
```

Provider-specific names belong only in adapter modules.

---

## 4. UX principles

### 4.1 Button-first

The default user experience must be button-first.

Good:

```text
[Record expense]
[Record income]
[Transfer between accounts]
[Upload statement]
[Review operations]
[Balance]
```

Avoid making command syntax the main path:

```text
/expense 3200 repair property_9maya
```

Commands may exist for power users, but the primary flow should guide the user
with buttons.

### 4.2 Narrow choices

Show only relevant choices.

```text
Good: 5 frequent categories + Other
Bad: 40 categories in one message
```

Prefer:

```text
most recently used accounts
favorite categories
frequent property/category pairs
workspace defaults
```

### 4.3 Confirm before posting

Every write flow should end with a confirmation card.

Example:

```text
Expense 3,200 RUB
Account: Cash
Category: Repairs
Property: 9 Maya 20

[Record] [Edit] [Cancel]
```

If confidence is low, create a draft or needs-review record instead of a
confirmed operation.

### 4.4 Special treatment for transfers

Internal transfer must be a first-class button.

```text
[Transfer between accounts]
```

This protects the critical invariant:

```text
Transfers move money between accounts.
Transfers do not affect income, expense, profit, or property ROI.
```

### 4.5 No accounting jargon

Do not expose internal terms like:

```text
Operation
MoneyEntry
ledger posting
affects_profit
raw transaction
dedupe hash
```

Use user language:

```text
expense
income
transfer
statement
needs checking
recorded
ignored
duplicate
```

---

## 5. Core scenarios

### 5.1 Record expense

Purpose:

```text
Capture everyday expenses before the user forgets them.
```

Flow:

```text
[Record expense]
  -> choose account
  -> enter or choose amount
  -> choose category
  -> choose optional property
  -> confirm
  -> create draft or confirmed operation according to permissions/settings
```

Default safety:

```text
If the user is not allowed to confirm records, create draft/needs_review.
If any required field is uncertain, create draft/needs_review.
```

### 5.2 Record income

Purpose:

```text
Capture cash rent, client payments, salary, refunds, and other income.
```

Flow:

```text
[Record income]
  -> choose receiving account
  -> choose income category
  -> choose optional property
  -> enter amount
  -> confirm
```

Important rule:

```text
Tenant security deposits are not income until retained.
```

Security deposits should have a dedicated guided path later if needed.

### 5.3 Transfer between accounts

Purpose:

```text
Record internal money movement without affecting profit.
```

Flow:

```text
[Transfer between accounts]
  -> choose source account
  -> choose destination account
  -> enter amount
  -> confirm
```

Result:

```text
Operation type: transfer
affects_profit: false
MoneyEntry: source account negative amount
MoneyEntry: destination account positive amount
```

### 5.4 Upload statement or document

Purpose:

```text
Let users forward PDFs and documents from the messenger.
```

Flow:

```text
User sends file
  -> bot asks whether to upload
  -> choose workspace if needed
  -> choose account if needed
  -> create UploadedDocument
  -> enter the same import pipeline as web upload
```

Rule:

```text
Channel-specific upload must not fork the parser pipeline.
```

### 5.5 Review operations

Purpose:

```text
Make short review decisions easy from the messenger.
```

Flow:

```text
[Review operations]
  -> show one item at a time
  -> user taps action
  -> next item appears
```

Useful actions:

```text
[Confirm]
[Category]
[Property]
[Transfer]
[Duplicate]
[Ignore]
[Open in Booker Tee]
```

For complex edits, send the user to the web UI.

### 5.6 Import notifications

Purpose:

```text
Bring the user back when an import needs attention.
```

Examples:

```text
Statement processed.
Rows found: 43
Need review: 6
Possible duplicates: 2

[Review] [Open Booker Tee]
```

```text
Statement could not be parsed.
The file was saved.

[Open document] [Try again later]
```

### 5.7 Daily review reminder

Purpose:

```text
Improve data completeness through gentle reminders.
```

Example:

```text
There are 3 operations waiting for review.

[Review now] [Remind tomorrow]
```

### 5.8 Balance and latest operations

Purpose:

```text
Give quick read-only checks in a private chat.
```

Private chat only by default:

```text
[Balance]
[Latest operations]
[Uncategorized]
```

Group chats should hide balances unless the workspace owner explicitly enables
them.

### 5.9 Shared chat activity feed

Purpose:

```text
Create transparency and accountability for family, team, or property workflows.
```

Examples:

```text
Anna recorded an expense: 3,200 RUB.
Category: Repairs
Property: 9 Maya 20
Status: needs review
```

```text
Max confirmed 12 imported rows.
2 rows still need review.
```

Shared feed messages must respect privacy settings and permissions.

---

## 6. Architecture direction

Use feature-driven architecture:

```text
src/app/features/chat_integrations/
  __init__.py
  models.py
  schemas.py
  repository.py
  service.py
  router.py
  permissions.py
  events.py
  providers/
    __init__.py
    base.py
    telegram.py
  conversations/
    __init__.py
    state.py
    flows.py
    renderer.py
  commands/
    __init__.py
    handlers.py
  notifications/
    __init__.py
    formatter.py
    dispatcher.py
```

Layer direction:

```text
Router -> Service -> Repository -> Model
Provider adapter -> Service -> Booker Tee feature services
```

The integration feature may call existing feature services:

```text
imports
ledger
accounts
categories
properties
workspaces
users
```

It must not bypass them by writing cross-feature database rows directly.

---

## 7. Provider boundary

Provider adapters translate external events into internal objects.

External Telegram webhook:

```text
Telegram update
```

Internal normalized event:

```text
InboundChatEvent
```

External Telegram message response:

```text
Telegram API sendMessage / editMessage / sendDocument
```

Internal provider command:

```text
OutboundChatMessage
```

The rest of Booker Tee should not know Telegram payload shapes.

Provider-neutral interfaces should cover:

```text
send_message
edit_message
answer_action
download_file
verify_webhook
```

Do not create a large inheritance tree. Prefer `Protocol` interfaces and small
dataclasses/Pydantic schemas.

---

## 8. Conversation model

The bot should be stateful enough to guide the user safely.

Example state:

```text
flow: record_expense
step: choose_category
workspace_id
actor_user_id
draft_payload_json
expires_at
```

Rules:

```text
1. Conversation state belongs to a workspace when financial data is involved.
2. Conversation state must expire.
3. Cancel must always be available.
4. Back/Edit should be available on confirmation cards.
5. A stale button press must not mutate financial data.
6. Idempotency keys must prevent duplicate writes from repeated webhook events.
```

---

## 9. Data model sketch

Initial entities:

```text
IntegrationConnection
- id
- workspace_id
- provider
- status
- display_name
- created_by_user_id
- created_at
- updated_at

ChatConversationBinding
- id
- workspace_id
- connection_id
- provider
- external_chat_id
- conversation_type: private/group/channel
- mode: personal_input/shared_feed/review
- notification_level
- is_active
- created_at
- updated_at

ChatIdentityBinding
- id
- workspace_id
- user_id
- connection_id
- provider
- external_user_id
- display_name
- is_active
- created_at
- updated_at

ChatConversationState
- id
- workspace_id
- binding_id
- user_id
- flow
- step
- state_payload_json
- idempotency_key
- expires_at
- created_at
- updated_at

IntegrationEventDelivery
- id
- workspace_id
- connection_id
- binding_id
- event_type
- idempotency_key
- status
- error_message
- sent_at
- created_at
```

Every query must be scoped by `workspace_id`.

Provider secrets and tokens must be stored separately from display/binding data
and must never be logged.

---

## 10. Domain events

The integration module should react to domain events instead of being called
from random places in the application.

Useful event names:

```text
import.document_uploaded
import.completed
import.failed
import.requires_review
raw_transaction.needs_review
raw_transaction.duplicate_detected
operation.draft_created
operation.confirmed
operation.ignored
operation.deleted_or_reversed
workspace.member_joined
```

Initial implementation can be synchronous and simple. Later it can move to a
queue without changing feature services.

---

## 11. Permissions and privacy

Private financial data must be protected by default.

Rules:

```text
1. Chat identity must be explicitly linked to a Booker Tee user.
2. Chat user actions must run through workspace membership and permission checks.
3. Group chats must not show balances by default.
4. Group chats must not show full bank descriptions by default.
5. Sensitive account details must be masked.
6. File uploads must preserve source metadata but avoid logging file content.
7. Button action tokens must be signed or stored server-side with expiry.
8. Webhooks must verify provider authenticity where the provider supports it.
9. Repeated webhook delivery must be idempotent.
```

Recommended default group message:

```text
Anna recorded an expense: 3,200 RUB.
Category: Repairs
Property: 9 Maya 20
Status: needs review
```

Avoid by default:

```text
Full card/account numbers
Full PDF text
Private account balances
Sensitive counterparty descriptions
```

---

## 12. Implementation phases

### Phase A - Architecture foundation

Goal:

```text
Create provider-neutral integration scaffolding without Telegram business logic
leaking into core services.
```

Deliverables:

```text
1. Feature package structure.
2. Provider-neutral schemas.
3. Provider Protocol.
4. Database models and migration for bindings/state/delivery logs.
5. Permission helpers.
6. Unit tests for provider-neutral message handling.
```

### Phase B - Outbound shared feed

Goal:

```text
Send safe notifications from Booker Tee to a connected chat.
```

Deliverables:

```text
1. Connect a workspace to one Telegram chat.
2. Send import completed/failed/requires-review notifications.
3. Send operation recorded/confirmed notifications.
4. Delivery log with idempotency.
```

Why first:

```text
Outbound notifications create value with lower financial mutation risk.
```

### Phase C - Private read-only bot

Goal:

```text
Let linked users inspect safe personal workspace information.
```

Deliverables:

```text
1. Start menu.
2. Review count.
3. Latest operations.
4. Private balance command/button.
5. Workspace selection when needed.
```

### Phase D - File upload

Goal:

```text
Let users send statements/documents into the same import pipeline.
```

Deliverables:

```text
1. Telegram document webhook.
2. File download adapter.
3. Create UploadedDocument through existing import service.
4. Preserve channel metadata.
5. Notify when processing completes or fails.
```

### Phase E - Button-first manual capture

Goal:

```text
Create safe draft operations from guided chat flows.
```

Deliverables:

```text
1. Record expense flow.
2. Record income flow.
3. Transfer between accounts flow.
4. Confirmation cards.
5. Draft/needs-review fallback.
6. Tests that transfers do not affect profit.
```

### Phase F - Interactive review

Goal:

```text
Let users process review items one card at a time.
```

Deliverables:

```text
1. Review queue.
2. Confirm/ignore/duplicate buttons.
3. Category/property selection buttons.
4. Open in Booker Tee link for complex edits.
5. Stale action and duplicate action protection.
```

### Phase G - Additional providers

Goal:

```text
Prove the architecture by adding a second provider without changing core flows.
```

Possible providers:

```text
Slack
Discord
Mattermost
WhatsApp Business
```

Acceptance criterion:

```text
New provider implements provider adapter interfaces only.
Core flow handlers remain provider-neutral.
```

---

## 13. Testing expectations

Prioritize tests for:

```text
1. Workspace isolation for every chat action.
2. Chat identity cannot act before explicit binding.
3. Viewer/uploader permissions cannot confirm financial records.
4. Expense flow creates the expected draft/operation shape.
5. Income flow creates profit-affecting records only when appropriate.
6. Transfer flow creates two money entries and does not affect profit.
7. Stale buttons cannot mutate data.
8. Replayed webhook events do not create duplicate operations/documents.
9. Group chat notification formatter hides private balances by default.
10. File uploads enter the existing import pipeline.
11. Provider-specific Telegram payloads are normalized before business logic.
```

Use sanitized fixtures only. Do not include real chat transcripts with private
financial data.

---

## 14. Code readability standard

This module should read as a story.

Good service method names:

```text
start_expense_flow
choose_expense_account
choose_expense_category
confirm_expense
cancel_current_flow
notify_import_requires_review
bind_chat_identity
```

Avoid vague names:

```text
process
handle
do_action
run
execute_callback
```

Acceptable generic names only at boundaries:

```text
handle_webhook
dispatch_event
```

Keep decisions close to the domain language:

```text
If this is a transfer, call the ledger transfer service.
If this is an upload, call the import document service.
If this is a review action, call the import review service.
```

Do not hide important financial behavior behind clever abstractions.

---

## 15. First implementation target

The recommended first vertical slice is:

```text
Telegram shared feed for import and operation events.
```

Reason:

```text
It gives immediate value, proves provider setup, tests privacy boundaries, and
does not yet allow accidental financial writes from chat.
```

The second vertical slice should be:

```text
Telegram private bot with read-only review counts and latest operations.
```

The third vertical slice should be:

```text
Telegram document upload into the existing import pipeline.
```

Manual capture and interactive review should come after the permission,
idempotency, and state machinery are proven.

---

## 16. Acceptance criteria for the integration architecture

The architecture is acceptable when:

```text
1. Telegram is only one provider adapter.
2. Core flows are provider-neutral.
3. Every financial action is workspace-scoped.
4. Every actor is mapped to a Booker Tee user before acting.
5. Group chat privacy defaults are conservative.
6. Writes are idempotent.
7. Manual capture uses button-first guided flows.
8. Transfers are impossible to record as income by accident in the main flow.
9. Uploaded files enter the same import pipeline as web uploads.
10. Tests cover permission, privacy, idempotency, and financial correctness.
```

