import json

import httpx
import pytest

from app.features.chat_integrations.providers.fake import FakeChatProvider
from app.features.chat_integrations.providers.telegram import TelegramUpdateNormalizer
from app.features.chat_integrations.providers.telegram_client import (
    TelegramBotClient,
    TelegramBotClientError,
    TelegramEditMessageTextPayloadBuilder,
    TelegramOutboundMessageSender,
    TelegramSendMessagePayloadBuilder,
)
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatDocument,
    ChatProviderCode,
    InboundChatEvent,
    InboundChatEventType,
    OutboundChatButton,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)


def test_telegram_normalizer_reads_text_message() -> None:
    event = TelegramUpdateNormalizer.normalize_update(
        {
            "update_id": 1001,
            "message": {
                "message_id": 10,
                "from": {
                    "id": 42,
                    "is_bot": False,
                    "first_name": "Anna",
                    "last_name": "Ivanova",
                    "username": "anna",
                    "language_code": "ru",
                },
                "chat": {
                    "id": 42,
                    "first_name": "Anna",
                    "type": "private",
                },
                "text": "/start",
            },
        }
    )

    assert event.provider == ChatProviderCode.TELEGRAM
    assert event.event_id == "1001"
    assert event.event_type == InboundChatEventType.MESSAGE
    assert event.text == "/start"
    assert event.source_message_id == "10"
    assert event.actor is not None
    assert event.actor.external_user_id == "42"
    assert event.actor.display_name == "Anna Ivanova"
    assert event.actor.username == "anna"
    assert event.conversation is not None
    assert event.conversation.external_chat_id == "42"
    assert event.conversation.conversation_type == ChatConversationType.PRIVATE


def test_telegram_normalizer_preserves_document_metadata() -> None:
    event = TelegramUpdateNormalizer.normalize_update(
        {
            "update_id": 1002,
            "message": {
                "message_id": 11,
                "from": {"id": 42, "is_bot": False, "first_name": "Anna"},
                "chat": {"id": -100, "title": "Booker Tee", "type": "supergroup"},
                "document": {
                    "file_id": "file-id",
                    "file_unique_id": "unique-file-id",
                    "file_name": "statement.pdf",
                    "mime_type": "application/pdf",
                    "file_size": 2048,
                },
            },
        }
    )

    assert event.event_type == InboundChatEventType.DOCUMENT
    assert event.conversation is not None
    assert event.conversation.conversation_type == ChatConversationType.GROUP
    assert event.document is not None
    assert event.document.file_id == "file-id"
    assert event.document.file_name == "statement.pdf"
    assert event.document.mime_type == "application/pdf"
    assert event.document.file_size == 2048


def test_telegram_normalizer_reads_callback_query() -> None:
    event = TelegramUpdateNormalizer.normalize_update(
        {
            "update_id": 1003,
            "callback_query": {
                "id": "callback-id",
                "from": {"id": 42, "is_bot": False, "first_name": "Anna"},
                "message": {
                    "message_id": 12,
                    "chat": {"id": 42, "type": "private", "first_name": "Anna"},
                    "text": "Record expense?",
                },
                "data": "expense:start",
            },
        }
    )

    assert event.event_id == "1003:callback:callback-id"
    assert event.event_type == InboundChatEventType.CALLBACK_QUERY
    assert event.callback_data == "expense:start"
    assert event.callback_query_id == "callback-id"
    assert event.source_message_id == "12"
    assert event.text == "Record expense?"


def test_telegram_send_message_payload_uses_inline_keyboard() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    message = OutboundChatMessage(
        conversation=conversation,
        text="Hello",
        buttons=((OutboundChatButton(text="Help", callback_data="help:show"),),),
    )

    payload = TelegramSendMessagePayloadBuilder.build(message)

    assert payload == {
        "chat_id": 42,
        "text": "Hello",
        "reply_markup": {"inline_keyboard": [[{"text": "Help", "callback_data": "help:show"}]]},
    }


def test_telegram_edit_message_payload_uses_source_message_id() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    message = OutboundChatMessage(
        conversation=conversation,
        text="Updated",
        buttons=((OutboundChatButton(text="Next", callback_data="review:next"),),),
        delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
    )

    payload = TelegramEditMessageTextPayloadBuilder.build(
        message=message,
        message_id="12",
    )

    assert payload == {
        "chat_id": 42,
        "message_id": 12,
        "text": "Updated",
        "reply_markup": {"inline_keyboard": [[{"text": "Next", "callback_data": "review:next"}]]},
    }


async def test_telegram_client_requests_get_updates() -> None:
    seen_payloads: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content))
        assert str(request.url) == "https://api.telegram.org/bottest-token/getUpdates"
        return httpx.Response(200, json={"ok": True, "result": [{"update_id": 12}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        updates = await TelegramBotClient(
            bot_token="test-token",
            http_client=http_client,
        ).get_updates(offset=10, timeout_seconds=30)

    assert updates == [{"update_id": 12}]
    assert seen_payloads == [
        {
            "offset": 10,
            "timeout": 30,
            "allowed_updates": ["message", "callback_query"],
        }
    ]


async def test_telegram_client_http_error_hides_bot_token() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"ok": False, "description": "Bad Request: query is too old"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(TelegramBotClientError) as exc_info:
            await TelegramBotClient(
                bot_token="test-token",
                http_client=http_client,
            ).get_updates(offset=10, timeout_seconds=30)

    error_text = str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert "test-token" not in error_text
    assert "getUpdates" in error_text
    assert "query is too old" in error_text


async def test_telegram_client_edits_message_text() -> None:
    seen_payloads: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content))
        assert str(request.url) == "https://api.telegram.org/bottest-token/editMessageText"
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 12}})

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    message = OutboundChatMessage(
        conversation=conversation,
        text="Updated",
        delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        await TelegramBotClient(
            bot_token="test-token",
            http_client=http_client,
        ).edit_message_text(message=message, message_id="12")

    assert seen_payloads == [{"chat_id": 42, "text": "Updated", "message_id": 12}]


async def test_telegram_outbound_sender_edits_callback_source_message() -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 12}})

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1:callback:callback-id",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=None,
        callback_query_id="callback-id",
        source_message_id="12",
    )
    response = OutboundChatMessage(
        conversation=conversation,
        text="Updated review",
        delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
        callback_notification="Готово",
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        await TelegramOutboundMessageSender.send_response(
            client=TelegramBotClient(bot_token="test-token", http_client=http_client),
            event=event,
            response=response,
        )

    assert requests == [
        (
            "/bottest-token/answerCallbackQuery",
            {"callback_query_id": "callback-id", "text": "Готово"},
        ),
        (
            "/bottest-token/editMessageText",
            {"chat_id": 42, "text": "Updated review", "message_id": 12},
        ),
    ]


async def test_telegram_outbound_sender_still_edits_when_callback_answer_fails() -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append((request.url.path, payload))
        if request.url.path.endswith("/answerCallbackQuery"):
            return httpx.Response(
                400,
                json={"ok": False, "description": "Bad Request: query is too old"},
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 12}})

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1:callback:callback-id",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=None,
        callback_query_id="callback-id",
        source_message_id="12",
    )
    response = OutboundChatMessage(
        conversation=conversation,
        text="Updated review",
        delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
        callback_notification="Готово",
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        await TelegramOutboundMessageSender.send_response(
            client=TelegramBotClient(bot_token="test-token", http_client=http_client),
            event=event,
            response=response,
        )

    assert requests == [
        (
            "/bottest-token/answerCallbackQuery",
            {"callback_query_id": "callback-id", "text": "Готово"},
        ),
        (
            "/bottest-token/editMessageText",
            {"chat_id": 42, "text": "Updated review", "message_id": 12},
        ),
    ]


async def test_telegram_outbound_sender_falls_back_when_edit_fails() -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append((request.url.path, payload))
        if request.url.path.endswith("/editMessageText"):
            return httpx.Response(
                200,
                json={"ok": False, "description": "Bad Request: message to edit not found"},
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 13}})

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1:callback:callback-id",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=None,
        callback_query_id="callback-id",
        source_message_id="12",
    )
    response = OutboundChatMessage(
        conversation=conversation,
        text="Updated review",
        delivery_mode=OutboundChatDeliveryMode.EDIT_SOURCE_MESSAGE,
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        await TelegramOutboundMessageSender.send_response(
            client=TelegramBotClient(bot_token="test-token", http_client=http_client),
            event=event,
            response=response,
        )

    assert requests == [
        ("/bottest-token/answerCallbackQuery", {"callback_query_id": "callback-id"}),
        (
            "/bottest-token/editMessageText",
            {"chat_id": 42, "text": "Updated review", "message_id": 12},
        ),
        ("/bottest-token/sendMessage", {"chat_id": 42, "text": "Updated review"}),
    ]


async def test_telegram_client_downloads_document_by_file_path() -> None:
    seen_requests: list[tuple[str, bytes]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append((request.url.path, request.content))
        if request.url.path.endswith("/getFile"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "file_id": "file-id",
                        "file_path": "documents/statement.pdf",
                    },
                },
            )
        return httpx.Response(200, content=b"%PDF-test")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        downloaded_file = await TelegramBotClient(
            bot_token="test-token",
            http_client=http_client,
        ).download_document(
            ChatDocument(
                file_id="file-id",
                file_name="statement.pdf",
                mime_type="application/pdf",
            )
        )

    assert downloaded_file.filename == "statement.pdf"
    assert downloaded_file.content_type == "application/pdf"
    assert downloaded_file.file_bytes == b"%PDF-test"
    assert seen_requests[0] == ("/bottest-token/getFile", b'{"file_id":"file-id"}')
    assert seen_requests[1] == ("/file/bottest-token/documents/statement.pdf", b"")


async def test_telegram_client_sets_webhook_with_secret_token() -> None:
    seen_payloads: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content))
        assert request.url.path == "/bottest-token/setWebhook"
        return httpx.Response(200, json={"ok": True, "result": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        await TelegramBotClient(
            bot_token="test-token",
            http_client=http_client,
        ).set_webhook(
            url="https://booker.example/chat-integrations/telegram/webhook",
            secret_token="secret",
            drop_pending_updates=True,
        )

    assert seen_payloads == [
        {
            "url": "https://booker.example/chat-integrations/telegram/webhook",
            "secret_token": "secret",
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": True,
        }
    ]


async def test_fake_provider_records_sent_messages() -> None:
    provider = FakeChatProvider()
    conversation = ChatConversation(
        provider=ChatProviderCode.FAKE,
        external_chat_id="test-chat",
        conversation_type=ChatConversationType.PRIVATE,
    )
    message = OutboundChatMessage(conversation=conversation, text="Hello")

    await provider.send_message(message)

    assert provider.sent_messages == [message]


def test_fake_provider_records_inbound_events() -> None:
    provider = FakeChatProvider()
    conversation = ChatConversation(
        provider=ChatProviderCode.FAKE,
        external_chat_id="test-chat",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.FAKE,
        event_id="event-1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=conversation,
        actor=None,
        text="hello",
    )

    provider.push_event(event)

    assert provider.inbound_events == [event]
