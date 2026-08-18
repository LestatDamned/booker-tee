# Chat Integrations

Статус: действующий product/architecture contract.

Chat integration — дополнительный input/output channel над Booker Tee use
cases, не второй финансовый продукт.

## Current scope

Реализован Telegram-oriented provider boundary:

- webhook receiver с проверкой secret token;
- local polling worker;
- fake provider для tests;
- dev-only identity linking page;
- workspace/user/conversation bindings;
- button-first routing;
- document upload;
- manual/review/dashboard/workspace handlers;
- privacy-safe notifications и delivery tracking.

Provider-neutral enums также допускают Matrix, но production Matrix adapter не
является текущим scope.

## Flow

```text
Telegram update / polling
  -> provider adapter
  -> InboundChatEvent
  -> ChatEventService
  -> actor + workspace resolution
  -> callback/message/document routing
  -> scenario handler/use case
  -> OutboundChatMessage
  -> provider delivery
```

Provider payload не проходит в ledger/imports напрямую.

## Runtime modes

```text
local       Telegram polling
production  Telegram webhook
tests       fake provider
```

Local polling:

```bash
BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED=true
BOOKER_TEE_TELEGRAM_MODE=polling
BOOKER_TEE_TELEGRAM_BOT_TOKEN=<test token>
uv run python -m app.features.chat_integrations.polling
```

Production webhook требует explicit public base URL, bot token, webhook secret
и secure application settings.

Совместимый случайный secret можно сгенерировать локально:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

После применения migrations и запуска production application webhook
регистрируется существующим runtime-клиентом:

```bash
uv run python -m app.features.chat_integrations.webhook
```

Команда не выводит bot token или webhook secret. Telegram update IDs хранятся
без provider payload в `telegram_webhook_updates`: completed updates не
обрабатываются повторно, а failed updates допускают повторную доставку.

## Boundaries

Chat code может:

- нормализовать provider event;
- разрешить identity/workspace;
- хранить короткий conversation state;
- читать button/text/document intent;
- вызывать существующие application services;
- форматировать безопасный response.

Chat code не может:

- дублировать ledger/import/reports business logic;
- выбирать financial meaning по provider payload;
- мутировать данные без `WorkspaceContext`;
- хранить business state только в callback data;
- подтверждать сомнительную операцию без review/confirmation;
- отправлять raw statement content в сообщения или логи.

## Workspace and privacy

- Private financial commands требуют связанную identity и active workspace.
- Group/channel scope ограничивается explicit binding/mode.
- Provider external IDs не являются authorization.
- Webhook secret проверяется до обработки.
- Tokens, raw updates, full documents и account numbers не логируются.
- Downloaded file передаётся в тот же import application flow и сохраняется до
  parse.

## UX

- Button-first, короткие варианты и понятный fallback.
- Финансово значимое действие подтверждается явно.
- Transfer показывается отдельно от income/expense.
- Сложный review открывает canonical web route.
- Сообщение не притворяется окончательным, если backend вернул blocking state.

## Persistence

Feature хранит:

- `IntegrationConnection`;
- `ChatConversationBinding`;
- `ChatIdentityBinding`;
- `ChatConversationState`;
- `IntegrationEventDelivery`.

Все workspace-owned записи и lookups scoped. Conversation state ограничен
сценарием и не заменяет domain entities.

## Tests

- provider normalization;
- webhook secret;
- identity/workspace isolation;
- callback token parsing;
- upload preservation;
- financial confirmation/idempotency;
- safe response and notification content;
- fake provider без сети.

Локальная внутренняя карта модуля находится в
`src/app/features/chat_integrations/README.md`.
