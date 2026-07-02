# Chat integrations module notes

`chat_integrations` отвечает за вход Booker Tee через мессенджеры и другие
чатовые каналы.

Главная цель модуля: дать пользователю простой button-first интерфейс и при
этом не сломать финансовую корректность, workspace isolation и privacy.

`docs/integrations/CHAT_INTEGRATIONS.md` остается продуктово-архитектурным
источником истины. Этот README является локальным контрактом для кода внутри
`src/app/features/chat_integrations/`.

## Product story

Читайте модуль как одну историю:

```text
external chat update
-> provider adapter normalizes it
-> front controller resolves actor and workspace
-> routing chain reads callback/text/document intent
-> scenario handler calls a use case
-> presenter builds a safe response
-> provider adapter sends the response
```

Telegram, Matrix, Slack, Discord или другой провайдер не должны менять эту
историю. Они меняют только адаптер.

## Provider strategy

```text
MVP provider: Telegram
Long-term independent provider: Matrix / Element
Test provider: fake
```

Telegram нужен первым, потому что пользователям он привычен. Matrix нужен на
перспективу, чтобы архитектура не зависела от одной коммерческой платформы.

Element рассматриваем как клиентский опыт Matrix, а не как отдельный доменный
провайдер.

## Runtime modes

```text
local development -> Telegram polling
production server -> Telegram webhook
automated tests   -> fake provider
```

Локальная разработка не должна требовать публичный URL. Production webhook
должен проверять Telegram `secret_token`. Тесты не должны требовать Telegram
token, сети или реального бота.

Local polling worker:

```bash
uv run python -m app.features.chat_integrations.polling
```

Required local settings:

```text
BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED=true
BOOKER_TEE_TELEGRAM_BOT_TOKEN=<test bot token>
BOOKER_TEE_TELEGRAM_MODE=polling
```

## Current architecture

Текущий поток внутри feature:

```text
router / polling worker
-> provider adapter
-> ChatEventService
-> routing chain
-> scenario handler
-> use case / existing Booker Tee feature service
-> presenter
-> OutboundChatMessage
```

Слои:

- `router.py` принимает HTTP webhook и отдает его application layer.
- `polling.py` или CLI worker получает updates через `getUpdates`.
- `providers/` переводит внешний payload в provider-neutral DTO.
- `service.py` является front controller: workspace resolution, private-chat guard,
  document path, callback chain, message chain, safe fallback.
- `routing/` реализует Chain of Responsibility для bound callback/text сценариев.
- `handlers/` содержит application-level scenario handlers: upload, manual,
  review, dashboard, workspace.
- `use_cases/` содержит бизнес-операции и read-side сценарии, сгруппированные по
  flow.
- `actions/` содержит provider-neutral callback/action DTOs and token parsers.
- `notifications/` форматирует и отправляет безопасные shared-feed сообщения.
- `presentation/` и `presenters.py` строят provider-neutral `OutboundChatMessage`
  responses.
- `repository.py` содержит только SQLAlchemy persistence для chat integration tables.
- `models.py` содержит только persistence models.
- `schemas.py` содержит provider-neutral DTO and enums.
- `permissions.py` содержит reusable permission checks.

Dependency direction:

```text
provider adapter -> schemas
router / polling worker -> service
service -> routing
routing -> handlers
handlers -> use_cases
use_cases -> repository / existing Booker Tee feature services
repository -> models
presenters -> schemas
```

`routing/__init__.py`, `handlers/__init__.py`, `actions/__init__.py` stay
docstring-only. Do not add re-export/barrel imports there.

## Refactoring direction

Модуль должен читаться как набор взрослых, узких сценариев, а не как один
большой bot service.

Главная архитектурная позиция:

```text
Chat integrations are an input/output channel over Booker Tee use cases.
They are not a second financial domain.
```

Chat code may:

```text
normalize provider updates
resolve chat actor and workspace context
store short-lived conversation state
read button/text/document intent
guide the user through button-first flows
format privacy-safe responses
call existing imports / ledger / reports / rules services
```

Chat code must not:

```text
duplicate ledger, imports, reports, category, property, or rule business logic
turn callback_data into a business state store
mutate financial records without resolving WorkspaceContext
make provider-specific code decide financial meaning
```

Current internal story:

```text
InboundChatEvent
-> ChatEventService.receive_inbound_event(...)
-> WorkspaceChatResolver.require_bound_workspace(...)
-> ChatBoundCallbackChain.answer_if_matches(...)
   or ChatBoundMessageChain.answer_if_matches(...)
-> ChatEventHandlers.<scenario>()
-> Chat<Scenario>EventHandler.<action>()
-> Chat<Scenario>Service.<use_case>()
-> TelegramMainMenuPresenter.show_<response>(...)
-> OutboundChatMessage
```

Naming balance:

- Class names provide the domain actor: `ChatContextResolver`,
  `ChatRequestReader`, `ChatFlowRouter`, `ChatResponsePresenter`.
- Method names provide the action and avoid repeating the class name:
  `resolve_for_event`, `read_from_event`, `route`, `present`.
- Variables stay short inside the story: `context`, `request`, `result`,
  `response`.
- Generic verbs are allowed only when the class name gives enough context.

Good:

```python
context = await self.context_resolver.resolve_for_event(event)
request = self.request_reader.read_from_event(event, context)
result = await self.flow_router.route(request)
return self.response_presenter.present(result)
```

Avoid:

```python
result = await self.dispatcher.dispatch(action, context)
return self.chat_response_presenter.present_chat_result(result)
```

Import rules:

- Prefer direct imports from the module that owns the concept.
- Avoid barrel modules and compatibility facades when direct imports are practical.
- If a temporary compatibility facade is needed during a mechanical refactor, remove
  it as soon as all callers have moved to direct imports.
- Do not add new re-exports to package `__init__.py` files.
- Do not import callback/action DTOs from a package root.

Good:

```python
from app.features.chat_integrations.actions.review import ChatReviewCallbackData
from app.features.chat_integrations.actions.workspace import ChatWorkspaceSelection
```

Avoid:

```python
from app.features.chat_integrations.actions import ChatReviewCallbackData
```

## Adding a new chat scenario

New code should enter through the narrowest layer that owns the decision.

For a new callback:

```text
1. Add or extend the DTO/parser in actions/<flow>.py.
2. Add the routing branch in routing/<flow>.py.
3. Call a scenario handler from handlers/<flow>.py.
4. Put business rules in use_cases/<flow>/...
5. Add presenter output in `presentation/<flow>.py` or `presenters.py` while the
   flow still has not been extracted.
6. Add tests at the behavior boundary.
```

For a new text-message step:

```text
1. Add a small `BoundMessageHandler` implementation.
2. Register it in `ChatBoundMessageChain.build(...)` in the intended order.
3. Keep parsing/state checks in the handler or use case, not in `service.py`.
```

For a new provider:

```text
1. Implement provider normalization into `InboundChatEvent`.
2. Implement outbound sending from `OutboundChatMessage`.
3. Do not duplicate routing, handlers, use cases, or presenters.
```

Do not add scenario-specific branches to `ChatEventService` unless the branch is
a true top-level event type boundary such as document, callback, message, or a
private/group guard.

Refactoring order:

```text
1. Keep ChatEventService thin: no callback/message scenario ladders.
2. Keep routing chains explicit and grouped by flow.
3. Split Telegram presenters by flow.
4. Split tests by the same flow boundaries.
5. Add permissions only as reusable policies, not inline provider checks.
```

Current test split:

```text
tests/chat_integrations/test_actions.py -> actions/* callback-data encoding and parsing
tests/chat_integrations/test_presentation.py -> presentation/* behavior
tests/chat_integrations/test_providers.py -> providers/* normalization, payloads, clients, and fakes
tests/chat_integrations/test_transport.py -> router, webhook, and polling entrypoints
tests/chat_integrations/test_notifications.py -> notifications/* formatting and delivery
tests/chat_integrations/test_use_cases.py -> pure use-case helpers and policies
tests/chat_integrations/test_identity_workspace.py -> identity binding and workspace resolution use cases
tests/chat_integrations/test_service_menu.py -> top-level service menu and safe fallback behavior
tests/chat_integrations/test_service_dashboard.py -> bound dashboard, status, summaries, balances, and workspace switching
tests/chat_integrations/test_service_upload.py -> upload instructions, document upload, account choice, and shared-feed notification
tests/chat_integrations/test_service_manual.py -> manual operation entry, editing, confirmation, and persistence
tests/chat_integrations/test_service_review_queue.py -> starting, navigating, and empty-state review queue flows
tests/chat_integrations/test_service_review_actions.py -> ignore, stale-button, confirmed-action, continuation, and suggestion flows
tests/chat_integrations/test_service_review_transfer.py -> transfer selection, account/pair confirmation, and confirmed transfer flows
tests/chat_integrations/test_service_review_confirmation.py -> category selection, category confirmation, and property confirmation flows
tests/chat_integrations/test_service_review_rules.py -> rule suggestion, save suggestion, manual pattern input, and manual pattern save flows
tests/chat_integrations/test_service_safety.py -> group-chat privacy and safe response behavior
```

Keep tests in `tests/chat_integrations/` split by behavior boundary. Do not create
shared test barrels or hidden fixture facades.

Запрещено:

```text
providers/ -> ledger.repository
providers/ -> imports.repository
providers/ -> workspaces.models permission decisions
routing / handlers / presenters -> raw SQLAlchemy session queries
templates / provider payloads -> business rules
```

## Current module map

Current foundation:

- `schemas.py` - provider-neutral chat DTOs and downloaded-file DTO.
- `actions/` - explicit callback/action DTOs grouped by flow: identity, upload,
  manual, review, summary, workspace.
- `providers/base.py` - small Protocols for provider adapters.
- `providers/telegram.py` - Telegram update normalization.
- `providers/telegram_client.py` - Telegram Bot API client, file downloader, and outbound
  payload builders.
- `providers/fake.py` - fake provider for tests.
- `routing/chain.py` - bound callback Chain of Responsibility assembly.
- `routing/message_chain.py` - bound text-message Chain of Responsibility assembly.
- `routing/protocols.py` - structural Protocols and routing callables.
- `routing/*.py` - small flow-specific callback handlers.
- `handlers/factory.py` - explicit `ChatEventHandlers` creator for scenario handlers.
- `handlers/*.py` - scenario handlers that translate routing decisions into use-case
  calls and presenter responses.
- `presentation/` - flow-specific presenter modules extracted from the legacy
  shared presenter file.
- `presentation/formatting.py` - shared Telegram date and money formatting.
- `presentation/dashboard.py` - private status, summary, category summary, and
  balances responses.
- `presentation/manual.py` - manual operation flow responses.
- `presentation/review.py` - review queue, confirmation, transfer, and rule
  suggestion responses.
- `presentation/workspace.py` - workspace switching and workspace label responses.
- `presentation/upload.py` - upload-flow responses.
- `use_cases/identity.py` - identity binding use cases.
- `use_cases/workspace.py` - workspace resolution and workspace switching.
- `use_cases/dashboard.py` - private status, summaries, and balances.
- `use_cases/action_tokens.py` - short action token generation.
- `use_cases/review/` - review queue, actions, confirmation, rules, transfer flow.
- `use_cases/manual/` - manual income/expense/transfer flow state and operations.
- `presenters.py` - remaining shared Telegram responses: menus, account-link notices,
  and safe fallbacks.
- `service.py` - provider-neutral front controller with workspace resolution.
- `polling.py` - local Telegram polling worker with per-update service/session wiring.
- `router.py` - local/test Telegram dev-link page and production Telegram webhook endpoint.
- `models.py` - integration connections, chat identity bindings, conversation bindings,
  conversation state, delivery logs.
- `repository.py` - workspace-scoped chat binding persistence.
- `application.py` - remaining shared application helpers and compatibility-free
  use-case wiring that has not yet moved to focused modules.
- `notifications/formatter.py` - privacy-safe shared chat notification text.
- `notifications/dispatcher.py` - shared feed delivery with provider registry and delivery log.
- `webhook.py` - Telegram webhook policy, URL builder, registrar, and update receiver.
- `errors.py` - module-specific application errors.

Target additions:

- `permissions.py` - chat action permission checks.

No compatibility facades:

```text
actions/__init__.py
handlers/__init__.py
routing/__init__.py
use_cases/__init__.py
```

These files should stay empty except for a package docstring. Import from the
module that owns the concept.

## Naming convention: Class.action

Code should show who performs an action.

Prefer method calls that read like:

```python
TelegramUpdateNormalizer.normalize_update(...)
ChatIdentityBinder.bind_telegram_user(...)
WorkspaceChatResolver.resolve_workspace(...)
ExpenseConversation.start(...)
ExpenseConversation.choose_account(...)
ExpenseConversation.confirm(...)
ImportNotificationFormatter.import_requires_review(...)
ChatDeliveryService.send_message(...)
```

Avoid generic free-floating functions when the actor is not obvious:

```python
process(...)
handle(...)
run(...)
execute(...)
do_action(...)
normalize(...)
dispatch(...)
```

Generic names are acceptable only at hard boundaries where the context is already
clear:

```python
router.handle_webhook(...)
PollingWorker.run(...)
EventDispatcher.dispatch(...)
```

Even then, the next call should become specific:

```python
event = TelegramUpdateNormalizer.normalize_update(payload)
await ChatEventService.receive_inbound_event(event)
```

Use classes when the name gives the reader an actor:

```text
TelegramUpdateNormalizer
TelegramPollingWorker
ChatEventService
WorkspaceChatResolver
ChatIdentityBinder
ExpenseConversation
TransferConversation
ReviewQueuePresenter
ImportNotificationFormatter
```

Prefer small policy/reader classes even for tiny rules when the actor name makes
the code clearer:

```python
TelegramCallbackDataPolicy.ensure_callback_data(...)
SensitiveTextMasker.mask_account_name(...)
ChatActionTokenBuilder.build_payload(...)
```

Use free functions only when the function is tiny, pure, and the domain meaning
is already obvious from the name. Do not use free functions for provider parsing
or workflow orchestration.

## Story-style service methods

Service methods should be named after user or system actions:

Good:

```python
async def bind_chat_identity(...)
async def start_private_chat(...)
async def record_expense_from_confirmation(...)
async def upload_document_from_chat(...)
async def notify_import_completed(...)
async def notify_import_requires_review(...)
async def answer_callback_query(...)
```

Avoid:

```python
async def process(...)
async def handle(...)
async def execute(...)
async def manage(...)
async def update(...)
```

The happy path should be visible before the details:

```python
async def record_expense_from_confirmation(command: ConfirmExpenseCommand) -> Operation:
    context = await workspace_resolver.require_context(command.actor, command.workspace_id)
    permissions.require_financial_write(context)
    draft = await conversations.require_expense_draft(command.action_token)
    operation = await ledger.create_manual_expense(context, draft.to_ledger_command())
    await conversations.finish(command.action_token)
    return operation
```

## Provider adapter rules

Provider adapters translate. They do not decide financial meaning.

Telegram adapter may:

```text
read update_id
read message / callback_query / document
read chat id and chat type
read Telegram user id
read document metadata
convert payload into InboundChatEvent
format provider-specific outbound payload
download files through Telegram API
```

Telegram adapter must not:

```text
choose workspace
confirm operation
classify income/expense/transfer
query ledger tables directly
decide whether a user can act
log full financial text or document content
store secrets in payloads
```

## Button and action-token rules

Telegram `callback_data` is limited to 1-64 bytes. Do not put JSON payloads,
workspace ids, financial data, or document ids directly into callback data.

Use short action tokens:

```text
exp:abc123
rev:def456
trf:ghi789
```

The server must resolve the action token from state storage:

```text
action_token
-> ChatConversationState
-> workspace_id
-> actor_user_id
-> flow
-> draft payload
-> expiry
```

Rules:

```text
1. Action tokens expire.
2. Action tokens are single-use when they mutate data.
3. Stale button presses must not mutate financial data.
4. Replayed Telegram updates must be idempotent.
5. Sensitive data never lives in callback_data.
```

## Conversation flow rules

Button-first means the user should mostly tap, not type.

Flow shape:

```text
start flow
-> choose workspace if needed
-> choose account/category/property from short lists
-> enter amount only when needed
-> show confirmation card
-> create draft/confirmed record according to permissions and confidence
```

Every flow must support:

```text
Cancel
Back or Edit on confirmation
expiry
idempotent final action
safe fallback to web UI for complex edits
```

Main flows:

```text
ExpenseConversation
IncomeConversation
TransferConversation
DocumentUploadConversation
ReviewConversation
```

## Privacy and permissions

Default posture:

```text
private chat can show more
group chat shows less
unlinked chat can do almost nothing
```

Rules:

```text
1. A chat actor must be linked to a Booker Tee user before financial actions.
2. Every action resolves WorkspaceContext before touching financial services.
3. Group chats do not show balances by default.
4. Group chats do not show full bank descriptions by default.
5. Account numbers and sensitive descriptions must be masked.
6. File content and full PDF text must not be logged.
7. Provider tokens and webhook secrets must never be logged.
```

Permission checks must reuse the workspace permission model. Chat-specific code
can narrow permissions, but must not bypass existing web permission checks.

## Integration with existing features

This module should call existing services, not duplicate their rules.

Use:

```text
imports service for UploadedDocument creation and parser pipeline entry
ledger service for manual income/expense/transfer creation
workspaces service/dependencies for user/workspace/membership resolution
accounts/categories/properties services for choice lists
reports services for read-only summaries
```

Do not:

```text
create Operation and MoneyEntry directly from provider code
create UploadedDocument by bypassing import service invariants
read cross-workspace data for convenience
reimplement category/property selection rules in Telegram-specific code
```

## Testing standard

Tests should describe the same story as the code.

Required test layers:

```text
provider normalization tests
fake provider tests
conversation state tests
permission tests
idempotency tests
privacy formatter tests
file upload handoff tests
financial correctness tests for income/expense/transfer flows
```

No test should require a real Telegram token unless it is explicitly marked as a
manual integration test.

Useful test names:

```python
test_telegram_normalizer_preserves_document_metadata()
test_expense_conversation_requires_linked_user()
test_transfer_confirmation_creates_non_profit_operation()
test_group_notification_hides_balance_by_default()
test_replayed_callback_does_not_create_duplicate_operation()
```

## Implementation phases

This plan is intentionally ordered. Do not skip identity, workspace, permission,
idempotency, and privacy foundations to reach manual write flows faster.

### Phase 1 - Provider-neutral foundation

Goal:

```text
Create the smallest provider-neutral surface that can normalize Telegram updates
and be tested without Telegram network access.
```

Build:

```text
schemas.py
providers/base.py
providers/telegram.py
providers/fake.py
settings
tests
```

Acceptance:

```text
1. Telegram message updates normalize into InboundChatEvent.
2. Telegram document updates preserve file id, file name, MIME type, and size.
3. Telegram callback queries normalize into InboundChatEvent.
4. callback_data limit is enforced through TelegramCallbackDataPolicy.
5. Fake provider can record inbound and outbound events in tests.
6. No test requires a real Telegram token.
```

### Phase 2 - Telegram client and local polling

Goal:

```text
Run a real Telegram bot locally without a public URL.
```

Build:

```text
providers/telegram_client.py
polling.py
router.py only if webhook skeleton is useful
basic ChatEventService
basic TelegramMainMenuPresenter
```

Behavior:

```text
local worker
-> getUpdates
-> TelegramUpdateNormalizer.normalize_update
-> ChatEventService.receive_inbound_event
-> safe reply through Telegram client
```

Acceptance:

```text
1. Local polling works with BOOKER_TEE_TELEGRAM_MODE=polling.
2. /start returns a safe welcome/main menu.
3. Unknown messages return a safe fallback.
4. Replayed update_id is ignored or handled idempotently.
5. No financial data is exposed before identity binding.
6. Telegram client is behind a provider interface.
```

Tests:

```text
Telegram client request construction
polling offset handling
idempotent update handling
safe /start response
```

### Phase 3 - Identity and workspace binding

Goal:

```text
Map Telegram users and chats to Booker Tee users, workspaces, and permissions.
```

Build:

```text
models.py
repository.py
migration
ChatIdentityBinder
WorkspaceChatResolver
ChatConversationBindingService
```

Required tables:

```text
IntegrationConnection
ChatConversationBinding
ChatIdentityBinding
ChatConversationState
IntegrationEventDelivery
```

Acceptance:

```text
1. Telegram user cannot perform financial action before binding.
2. Bound Telegram user maps to a Booker Tee user.
3. Workspace selection is explicit when user has multiple workspaces.
4. Every binding query is scoped by workspace_id where financial data is involved.
5. Group chat binding can be enabled without exposing balances.
```

Tests:

```text
unbound user rejection
identity binding
workspace binding
workspace isolation
group privacy defaults
```

### Phase 4 - Private read-only bot

Goal:

```text
Give linked users useful private information without allowing mutations yet.
```

Build:

```text
PrivateStatusPresenter
ReviewCountQuery
LatestOperationsPresenter
PrivateBalancePresenter
```

Current implemented slice:

```text
ChatPrivateStatusReader
TelegramMainMenuPresenter.show_bound_menu
TelegramDashboardPresenter.show_private_status
TelegramMainMenuPresenter.show_group_private_actions_notice
ChatDocumentUploadService.start_document_upload
ChatDocumentUploadService.complete_document_upload
ChatReviewUrlBuilder.build_imports_url
ChatReviewUrlBuilder.build_document_review_url
ChatImportNotificationFormatter.format_document_uploaded
ChatSharedFeedNotificationService.notify_import_document_uploaded
ChatBoundMenuCallbackHandler main menu and status callbacks
```

Menu:

```text
[Review operations]
[Latest operations]
[Balance]
[Upload statement]
```

Acceptance:

```text
1. Private chat can show review count.
2. Private chat can show latest operations with masked sensitive text.
3. Private balance works only for linked users with permission.
4. Group chats cannot access private balance by default.
5. Read queries reuse existing feature services or read-side query objects.
```

### Phase 5 - Shared chat feed

Goal:

```text
Notify a family/team/property chat about safe Booker Tee activity.
```

Build:

```text
notifications/formatter.py
notifications/dispatcher.py
IntegrationEventDelivery repository methods
domain event subscribers or synchronous event hooks
```

Events:

```text
import.completed
import.failed
import.requires_review
operation.draft_created
operation.confirmed
raw_transaction.duplicate_detected
```

Acceptance:

```text
1. Shared feed hides balances by default.
2. Shared feed masks sensitive account and bank details.
3. Delivery is idempotent by event id.
4. Failed delivery is recorded without crashing the financial workflow.
5. Telegram-specific formatting stays inside provider/notification boundary.
```

### Phase 6 - Telegram document upload

Goal:

```text
Let a user send a PDF statement to Telegram and enter the existing import pipeline.
```

Build:

```text
TelegramFileDownloader
DocumentUploadConversation
ChatUploadService
source channel metadata on UploadedDocument if missing
```

Flow:

```text
Telegram document
-> confirm upload
-> choose workspace/account when needed
-> download file
-> create UploadedDocument through imports service
-> parser pipeline continues unchanged
```

Acceptance:

```text
1. Telegram document upload never bypasses imports service invariants.
2. File name and MIME type are preserved from Telegram Document metadata.
3. File size limits are enforced before download where possible.
4. Same file can be uploaded twice without double-counting confirmed ledger data.
5. Parser failures preserve document and parse attempt data.
```

### Phase 7 - Button-first manual capture

Goal:

```text
Let users record common manual money events through guided buttons.
```

Build:

```text
ExpenseConversation
IncomeConversation
TransferConversation
ChatConversationState repository
action token generation and expiry
confirmation presenters
```

Main buttons:

```text
[Record expense]
[Record income]
[Transfer between accounts]
```

Acceptance:

```text
1. User chooses from short account/category/property lists.
2. Amount entry is the only common free-text step.
3. Confirmation card appears before mutation.
4. Transfer flow creates transfer operation only, never income.
5. Low-confidence or low-permission actions create draft/needs_review.
6. Stale action tokens cannot mutate financial data.
7. Replayed callback cannot create duplicate operation.
```

Tests:

```text
expense happy path
income happy path
transfer does not affect profit
stale token rejection
replayed callback idempotency
permission rejection
```

### Phase 8 - Interactive review queue

Goal:

```text
Let users clear simple review items one card at a time from a private chat.
```

Build:

```text
ReviewConversation
ReviewQueuePresenter
ReviewActionService
category/property selection presenters
open-in-web links
```

Current implemented slice:

```text
ChatBoundCallbackChain callback routing
ChatBoundMessageChain text-message routing
ChatEventHandlers explicit scenario handler creation
ChatReviewQueueCallbackHandler review navigation callbacks
ChatReviewActionCallbackHandler review action callbacks
ChatReviewConfirmationCallbackHandler category/property callbacks
ChatReviewTransferCallbackHandler transfer callbacks
ChatReviewRuleSuggestionCallbackHandler rule suggestion callbacks
ChatWorkspaceCallbackHandler workspace callbacks
ChatDashboardCallbackHandler summary and balance callbacks
ChatBoundMenuCallbackHandler menu/manual-start fallback callbacks
ChatReviewRulePatternMessageHandler manual rule-pattern text messages
ChatReviewQueueReader.read_next_item
ChatReviewQueueReader.read_item
ChatIntegrationRepository.try_consume_active_conversation_state
ChatIntegrationRepository.deactivate_other_identity_bindings
ChatWorkspaceSwitcher.start_workspace_selection
ChatWorkspaceSwitcher.select_workspace
ChatMonthlySummaryReader.read_current_month_summary
ChatMonthlySummaryReader.read_month_summary
ChatMonthlySummaryReader.read_category_summary
ChatAccountBalanceReader.read_account_balances
ChatAccountBalanceTotalBuilder.build_totals
ChatMonthRange.next_month_start
ChatReviewQueueService.start_next_review_item
ChatReviewQueueService.return_to_review_item
ChatReviewActionService.apply_action
ChatReviewActionService.start_action_confirmation
ChatReviewActionService.confirm_action
ChatReviewConfirmationService.start_category_selection
ChatReviewConfirmationService.confirm_with_category
ChatReviewConfirmationService.confirm_with_property
ChatReviewConfirmationService.confirm_with_suggestion
ChatReviewConfirmationService.change_category_page
ChatReviewRuleSuggestionService.save_suggestion
ChatReviewRuleSuggestionService.skip_suggestion
ChatReviewRuleSuggestionService.start_pattern_selection
ChatReviewRuleSuggestionService.start_manual_pattern_input
ChatReviewRuleSuggestionService.save_pattern_selection
ChatReviewRuleSuggestionService.save_manual_pattern
ChatReviewTransferService.start_transfer_selection
ChatReviewTransferService.start_transfer_confirmation_with_account
ChatReviewTransferService.start_transfer_confirmation_with_pair
ChatReviewTransferService.confirm_transfer
ChatReviewCallbackData short action tokens
ChatReviewCallbackData accept-suggestion action
ChatReviewActionConfirmationCallbackData short confirmation token
ChatReviewReturnCallbackData return-to-row token
ChatReviewCategoryCallbackData short category tokens
ChatReviewCategoryPageCallbackData short category page tokens
ChatReviewPropertyCallbackData short property tokens
ChatReviewTransferCallbackData short transfer account tokens
ChatReviewTransferPairCallbackData short transfer pair tokens
ChatReviewTransferConfirmationCallbackData short transfer confirmation token
ChatReviewRuleSuggestionCallbackData short rule action tokens
ChatReviewRulePatternCallbackData short rule pattern tokens
ChatWorkspaceCallbackData short workspace tokens
ChatSummaryCallbackData short month summary tokens
TelegramWorkspacePresenter.show_menu
TelegramWorkspacePresenter.show_switch_error
TelegramDashboardPresenter.show_monthly_summary
TelegramDashboardPresenter.show_category_summary
TelegramDashboardPresenter.show_account_balances
TelegramManualPresenter manual operation flow screens
TelegramReviewPresenter review queue and action screens
TelegramReviewActionErrorPresenter stale-button detection
ChatReviewStateClaimer one-time final action claim
OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE for review workspaces
TelegramOutboundMessageSender editMessageText fallback to sendMessage
```

Card shape:

```text
one raw transaction per message
full operation details for the private user
short suggested action summary
safe open-in-web link
short action token stored in chat_conversation_states
safe status mutations: ignore, mark as unique, duplicate for possible_duplicate rows
ignore and duplicate mutations require an explicit confirmation screen
confirm mutation requires a separate category-selection step
if active properties exist, confirm mutation requires a property/no-property choice
transfer mutation requires a separate counterparty account-selection step
transfer mutation can use a matched raw transaction when a pair candidate exists
transfer mutation requires an explicit final confirmation screen
```

Actions:

```text
[Next]
[Open in Booker Tee]
[Confirm]
[Ignore]
[This is unique]
[Category] implemented as the confirm gate
[Accept suggestion] confirms the suggested category when it is available
[Property] optional confirm gate when workspace has active properties
[Transfer] implemented with matched raw row or explicit counterparty account choice
[Confirm transfer] final explicit transfer gate
[Duplicate] only for rows already marked possible_duplicate
[Prev category page]
[Next category page]
```

Acceptance:

```text
1. Each card is scoped to one workspace.
2. Complex edits route to web UI.
3. Confirm/ignore/duplicate actions reuse import review services.
4. Category/property choices are short and workspace-scoped.
5. Stale or repeated buttons do not mutate records twice.
6. Confirming into accounting requires explicit category choice.
7. Property choice is explicit: users choose an active property or "No property".
8. Transfer confirmation requires explicit matched raw row or counterparty account choice.
9. Matched raw rows are suggested before account fallback when candidates exist.
10. Duplicate action is only visible when the row status is possible_duplicate and
    the card shows the review reason.
11. Suggested category confirmation is a separate explicit action.
12. Category lists are pageable and keep stable global indexes in callback state.
13. Review screens are edited in-place when the provider supports message edits.
14. Ignore and duplicate actions show a consequence-focused confirmation first.
15. Transfer posting shows a consequence-focused confirmation first.
16. Expired or already-consumed review buttons show a simple stale-button message.
17. Final review mutations atomically claim their chat state before posting.
18. Manual category confirmation can offer a user-approved suggestion rule.
19. Rule suggestions show the inferred merchant pattern and alternative patterns.
20. Users can type a custom rule pattern when inferred patterns are too noisy.
21. After a final row action, review continues after that row before returning to
    earlier skipped rows.
```

### Phase 9 - Webhook production mode

Goal:

```text
Support production Telegram webhook delivery after polling is proven locally.
```

Build:

```text
router.py
TelegramWebhookVerifier
setWebhook/deleteWebhook helper command if useful
```

Acceptance:

```text
1. Webhook endpoint verifies X-Telegram-Bot-Api-Secret-Token.
2. Webhook and polling modes remain mutually exclusive in runtime config.
3. Invalid webhook requests are rejected.
4. Webhook update handling reuses the same ChatEventService as polling.
```

### Phase 10 - Matrix provider spike

Goal:

```text
Prove provider-neutral architecture with a second provider.
```

Build:

```text
providers/matrix.py
MatrixUpdateNormalizer
Matrix outbound adapter
fake Matrix fixtures
```

Acceptance:

```text
1. Matrix provider plugs into the same ChatEventService.
2. Conversation flows do not import Telegram modules.
3. Provider-specific differences stay inside providers/matrix.py.
4. Tests prove at least one read-only flow works through Matrix fixtures.
```

## Next implementation slice

```text
review action UX hardening
latest confirmed operations
short import/review completion summary
```

## Near-term bot roadmap

Keep the bot split into three simple modes.

```text
1. Проверка
2. Сводка
3. Рабочее пространство
```

### 1. Проверка

Goal:

```text
Clear imported rows quickly with button-first actions and minimal chat history noise.
```

Next steps:

```text
1. Keep one editable review message whenever the provider supports it.
```

Rule suggestion flow:

```text
user chooses category manually
-> operation is confirmed safely
-> bot shows a compact "remember this?" prompt
-> user taps "Запомнить", chooses another suggested pattern, types a custom pattern,
   or taps "Не сейчас"
-> if accepted, create a workspace-scoped transaction rule
```

First rule shape:

```text
if normalized description contains a stable merchant/counterparty fragment
then suggest category_id for future imported rows in the same workspace
```

Rules:

```text
1. Never create rules automatically.
2. Suggest rules only after the user manually chose a category.
3. Show exactly what will be remembered before creating the rule.
4. Do not suggest rules for overly generic or noisy descriptions.
5. Rules suggest/prefill future rows; risky matches still stay reviewable.
6. Manual patterns are cleaned and rejected when too short or card-number-like.
```

### 2. Сводка

Goal:

```text
Let a linked private user check financial state without opening the web app.
```

First read-only screens:

```text
1. Month summary with previous/current/next month navigation. [implemented]
2. Accounts and balances grouped by currency. [implemented]
3. Category detail for the selected month. [implemented]
4. Latest 5 confirmed operations.
5. Review/import counters. [implemented]
6. Property summary when operations are linked to properties.
```

Rules:

```text
1. Private chat only by default.
2. Always show the active workspace name.
3. Use existing reports/read-side services.
4. Mask sensitive descriptions where possible.
5. Never expose balances in group chats by default.
```

### 3. Рабочее пространство

Goal:

```text
Make the active workspace explicit and easy to change before uploads, reports, and manual actions.
```

First flow:

```text
current workspace card
-> list accessible workspaces
-> choose workspace by button
-> make the selected Telegram identity binding active
-> redraw main menu with the selected workspace
```

Acceptance:

```text
1. Every financial chat action resolves a WorkspaceContext.
2. The user can see the active workspace before mutating data.
3. Switching workspace never exposes data from another workspace.
4. Upload, review, manual operation, reports, and balances use the selected workspace.
5. Callback data stores only a short token and index; workspace ids stay in server state.
```

## Quality bar

The module is ready only when a new programmer can read the main path and retell
it in product language.

Good signs:

```text
The actor is visible.
The action is named.
The workspace boundary is explicit.
The permission check is easy to find.
The provider adapter translates and stops.
The service tells the business story.
The repository only persists.
The tests read like scenarios.
```

Bad signs:

```text
Generic process/handle functions hide important decisions.
Telegram payloads leak into ledger/imports/workspaces.
callback_data contains business payloads.
Provider code writes financial rows.
Group messages expose sensitive financial detail.
One function both parses Telegram and confirms money movement.
```

If code and this README disagree, fix the code or update this README in the same
change.
