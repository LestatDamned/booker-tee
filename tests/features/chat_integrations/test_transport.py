import json
from typing import cast

import httpx
import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.polling import TelegramPollingWorker
from app.features.chat_integrations.providers.telegram_client import TelegramBotClient
from app.features.chat_integrations.router import ChatIntegrationDevModePolicy
from app.features.chat_integrations.schemas import (
    InboundChatEvent,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)
from app.features.chat_integrations.webhook import (
    TelegramWebhookRegistrar,
    TelegramWebhookSecretPolicy,
    TelegramWebhookUpdateReceiver,
    TelegramWebhookUrlBuilder,
)


def test_chat_integration_dev_mode_rejects_production_settings() -> None:
    with pytest.raises(HTTPException) as exc_info:
        ChatIntegrationDevModePolicy.require_dev_mode(Settings(environment="production"))
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_telegram_webhook_secret_policy_rejects_wrong_secret() -> None:
    settings = Settings(
        chat_integrations_enabled=True,
        telegram_mode="webhook",
        telegram_bot_token="test-token",
        telegram_webhook_secret="correct-secret",
    )

    with pytest.raises(HTTPException) as exc_info:
        TelegramWebhookSecretPolicy.require_valid_secret(
            settings=settings,
            received_secret="wrong-secret",
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


def test_telegram_webhook_url_builder_uses_public_base_url() -> None:
    settings = Settings(public_base_url="https://booker.example/")

    webhook_url = TelegramWebhookUrlBuilder.build_public_webhook_url(settings)

    assert webhook_url == "https://booker.example/chat-integrations/telegram/webhook"


@pytest.mark.asyncio
async def test_telegram_webhook_registrar_sets_public_webhook() -> None:
    seen_payloads: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content))
        assert request.url.path == "/bottest-token/setWebhook"
        return httpx.Response(200, json={"ok": True, "result": True})

    settings = Settings(
        chat_integrations_enabled=True,
        telegram_mode="webhook",
        telegram_bot_token="test-token",
        telegram_webhook_secret="secret",
        public_base_url="https://booker.example",
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        webhook_url = await TelegramWebhookRegistrar(
            settings=settings,
            http_client=http_client,
        ).register_webhook(drop_pending_updates=True)

    assert webhook_url == "https://booker.example/chat-integrations/telegram/webhook"
    assert seen_payloads == [
        {
            "url": webhook_url,
            "secret_token": "secret",
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True,
        }
    ]


@pytest.mark.asyncio
async def test_telegram_webhook_receiver_sends_service_response() -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    settings = Settings(
        chat_integrations_enabled=True,
        telegram_mode="webhook",
        telegram_bot_token="test-token",
        telegram_webhook_secret="secret",
    )
    update: dict[str, object] = {
        "update_id": 100,
        "message": {
            "message_id": 1,
            "chat": {"id": 42, "type": "private", "first_name": "Anna"},
            "text": "/start",
        },
    }

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        await TelegramWebhookUpdateReceiver(
            session=cast(AsyncSession, object()),
            settings=settings,
            http_client=http_client,
        ).receive_update(update)

    assert requests[0][0] == "/bottest-token/sendMessage"
    assert requests[0][1]["chat_id"] == 42
    assert "Booker Tee" in str(requests[0][1]["text"])


@pytest.mark.asyncio
async def test_polling_worker_updates_offset_and_sends_start_response() -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append((request.url.path, payload))
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 100,
                            "message": {
                                "message_id": 1,
                                "from": {"id": 42, "is_bot": False, "first_name": "Anna"},
                                "chat": {"id": 42, "type": "private", "first_name": "Anna"},
                                "text": "/start",
                            },
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        worker = TelegramPollingWorker(
            client=TelegramBotClient(bot_token="test-token", http_client=http_client),
            timeout_seconds=30,
        )

        handled_count = await worker.run_once()

    assert handled_count == 1
    assert worker.next_offset == 101
    assert requests[0] == (
        "/bottest-token/getUpdates",
        {"timeout": 30, "allowed_updates": ["message", "callback_query"]},
    )
    assert requests[1][0] == "/bottest-token/sendMessage"
    assert requests[1][1]["chat_id"] == 42
    assert "Booker Tee" in str(requests[1][1]["text"])


@pytest.mark.asyncio
async def test_polling_worker_edits_review_callback_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    class FakeChatEventService:
        def __init__(self, *args: object) -> None:
            pass

        async def receive_inbound_event(self, event: InboundChatEvent):
            assert event.callback_query_id == "callback-id"
            assert event.source_message_id == "12"
            assert event.conversation is not None
            return OutboundChatMessage(
                conversation=event.conversation,
                text="Updated review",
                delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
            )

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append((request.url.path, payload))
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 100,
                            "callback_query": {
                                "id": "callback-id",
                                "from": {"id": 42, "is_bot": False, "first_name": "Anna"},
                                "message": {
                                    "message_id": 12,
                                    "chat": {
                                        "id": 42,
                                        "type": "private",
                                        "first_name": "Anna",
                                    },
                                    "text": "Review",
                                },
                                "data": "review:next",
                            },
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 12}})

    monkeypatch.setattr(
        "app.features.chat_integrations.polling.ChatEventService",
        FakeChatEventService,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        worker = TelegramPollingWorker(
            client=TelegramBotClient(bot_token="test-token", http_client=http_client),
            timeout_seconds=30,
        )

        handled_count = await worker.run_once()

    assert handled_count == 1
    assert requests[1] == (
        "/bottest-token/answerCallbackQuery",
        {"callback_query_id": "callback-id"},
    )
    assert requests[2] == (
        "/bottest-token/editMessageText",
        {"chat_id": 42, "text": "Updated review", "message_id": 12},
    )


@pytest.mark.asyncio
async def test_polling_worker_ignores_replayed_update_id() -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append((request.url.path, payload))
        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 100,
                            "message": {
                                "message_id": 1,
                                "chat": {"id": 42, "type": "private", "first_name": "Anna"},
                                "text": "/start",
                            },
                        },
                        {
                            "update_id": 100,
                            "message": {
                                "message_id": 1,
                                "chat": {"id": 42, "type": "private", "first_name": "Anna"},
                                "text": "/start",
                            },
                        },
                    ],
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        worker = TelegramPollingWorker(
            client=TelegramBotClient(bot_token="test-token", http_client=http_client),
            timeout_seconds=30,
        )

        handled_count = await worker.run_once()

    send_message_requests = [path for path, _payload in requests if path.endswith("/sendMessage")]
    assert handled_count == 1
    assert send_message_requests == ["/bottest-token/sendMessage"]
