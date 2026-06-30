import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations import application as chat_application
from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.commands import (
    BindChatIdentityCommand,
    ChatManualAccountSelection,
    ChatManualCategorySelection,
    ChatManualConfirmationSelection,
    ChatManualCorrectionSelection,
    ChatManualDescriptionSelection,
    ChatReviewActionSelection,
    ChatReviewCallbackData,
    ChatReviewCategoryCallbackData,
    ChatReviewCategoryPageCallbackData,
    ChatReviewCategoryPageSelection,
    ChatReviewCategorySelection,
    ChatReviewNavigationCallbackData,
    ChatReviewNavigationSelection,
    ChatReviewPropertyCallbackData,
    ChatReviewPropertySelection,
    ChatReviewTransferAccountSelection,
    ChatReviewTransferCallbackData,
    ChatReviewTransferPairCallbackData,
    ChatReviewTransferPairSelection,
)
from app.features.chat_integrations.errors import (
    ChatIdentityBindingError,
    ChatWorkspaceResolutionError,
)
from app.features.chat_integrations.notifications import dispatcher as notification_dispatcher
from app.features.chat_integrations.notifications.dispatcher import (
    ChatNotificationProviderRegistry,
    ChatSharedFeedNotificationService,
)
from app.features.chat_integrations.notifications.formatter import (
    ChatImportNotificationFormatter,
    ImportDocumentUploadedNotification,
)
from app.features.chat_integrations.polling import TelegramPollingWorker
from app.features.chat_integrations.presenters import TelegramMainMenuPresenter
from app.features.chat_integrations.providers.fake import FakeChatProvider
from app.features.chat_integrations.providers.telegram import (
    TelegramCallbackDataPolicy,
    TelegramUpdateNormalizationError,
    TelegramUpdateNormalizer,
)
from app.features.chat_integrations.providers.telegram_client import (
    TelegramBotClient,
    TelegramEditMessageTextPayloadBuilder,
    TelegramOutboundMessageSender,
    TelegramSendMessagePayloadBuilder,
)
from app.features.chat_integrations.router import ChatIntegrationDevModePolicy
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatDocument,
    ChatProviderCode,
    ChatUser,
    InboundChatEvent,
    InboundChatEventType,
    OutboundChatButton,
    OutboundChatDeliveryMode,
    OutboundChatMessage,
)
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.webhook import (
    TelegramWebhookRegistrar,
    TelegramWebhookSecretPolicy,
    TelegramWebhookUpdateReceiver,
    TelegramWebhookUrlBuilder,
)
from app.features.imports.models import UploadedDocumentStatus
from app.features.ledger.models import OperationType
from app.features.workspaces.service import WorkspaceContext


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


def test_telegram_callback_data_is_limited_to_64_bytes() -> None:
    assert TelegramCallbackDataPolicy.ensure_callback_data("expense:start") == "expense:start"

    with pytest.raises(TelegramUpdateNormalizationError):
        TelegramCallbackDataPolicy.ensure_callback_data("x" * 65)


def test_chat_review_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewCallbackData.build_ignore_action(action_token="shorttoken")

    assert len(callback_data) <= 64
    assert callback_data == "rev:shorttoken:ign"
    assert ChatReviewCallbackData.parse_action(callback_data) is not None
    assert ChatReviewCallbackData.build_duplicate_action(action_token="shorttoken") == (
        "rev:shorttoken:dup"
    )
    assert ChatReviewCallbackData.build_accept_suggestion_action(action_token="shorttoken") == (
        "rev:shorttoken:sug"
    )
    assert ChatReviewCallbackData.parse_action("review:next") is None


def test_chat_review_navigation_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewNavigationCallbackData.build_next_action(
        action_token="shorttoken",
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvn:shorttoken:next"
    assert ChatReviewNavigationCallbackData.parse_navigation_selection(callback_data) == (
        ChatReviewNavigationSelection(action_token="shorttoken", direction="next")
    )
    assert (
        ChatReviewNavigationCallbackData.build_previous_action(action_token="shorttoken")
        == "rvn:shorttoken:prev"
    )
    assert ChatReviewNavigationCallbackData.parse_navigation_selection("review:next") is None


def test_chat_review_category_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewCategoryCallbackData.build_category_selection(
        action_token="shorttoken",
        category_index=2,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvc:shorttoken:2"
    assert ChatReviewCategoryCallbackData.parse_category_selection(callback_data) == (
        ChatReviewCategorySelection(action_token="shorttoken", category_index=2)
    )
    assert ChatReviewCategoryCallbackData.parse_category_selection("rev:shorttoken:conf") is None


def test_chat_review_category_page_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewCategoryPageCallbackData.build_page_action(
        action_token="shorttoken",
        page_index=2,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rcp:shorttoken:2"
    assert ChatReviewCategoryPageCallbackData.parse_page_selection(callback_data) == (
        ChatReviewCategoryPageSelection(action_token="shorttoken", page_index=2)
    )
    assert ChatReviewCategoryPageCallbackData.parse_page_selection("rvc:shorttoken:2") is None


def test_chat_review_property_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewPropertyCallbackData.build_property_selection(
        action_token="shorttoken",
        property_index=3,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvp:shorttoken:3"
    assert ChatReviewPropertyCallbackData.parse_property_selection(callback_data) == (
        ChatReviewPropertySelection(action_token="shorttoken", property_index=3)
    )
    assert ChatReviewPropertyCallbackData.parse_property_selection("rvc:shorttoken:3") is None


def test_chat_review_transfer_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewTransferCallbackData.build_account_selection(
        action_token="shorttoken",
        account_index=1,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvt:shorttoken:1"
    assert ChatReviewTransferCallbackData.parse_account_selection(callback_data) == (
        ChatReviewTransferAccountSelection(action_token="shorttoken", account_index=1)
    )
    assert ChatReviewTransferCallbackData.parse_account_selection("rvp:shorttoken:1") is None


def test_chat_review_transfer_pair_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewTransferPairCallbackData.build_pair_selection(
        action_token="shorttoken",
        pair_index=1,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvx:shorttoken:1"
    assert ChatReviewTransferPairCallbackData.parse_pair_selection(callback_data) == (
        ChatReviewTransferPairSelection(action_token="shorttoken", pair_index=1)
    )
    assert ChatReviewTransferPairCallbackData.parse_pair_selection("rvt:shorttoken:1") is None


def test_review_item_shows_duplicate_action_only_for_possible_duplicate() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )

    def review_item(status: str) -> chat_application.ChatReviewQueueItem:
        return chat_application.ChatReviewQueueItem(
            document_id=uuid4(),
            raw_transaction_id=uuid4(),
            row_index=0,
            status=status,
            account_name="T-Bank Card",
            operation_date=date(2026, 6, 30),
            amount=Decimal("-1250.00"),
            amount_raw=None,
            currency="RUB",
            description="MAGNIT",
            suggested_operation_type="expense",
            normalization_error="Possible duplicate.",
        )

    possible_duplicate = TelegramMainMenuPresenter.show_next_review_item(
        conversation,
        review_item("possible_duplicate"),
        action_token="reviewtoken",
    )
    needs_review = TelegramMainMenuPresenter.show_next_review_item(
        conversation,
        review_item("needs_review"),
        action_token="reviewtoken",
    )

    assert possible_duplicate.buttons[1][0].callback_data == "rev:reviewtoken:dup"
    assert possible_duplicate.buttons[1][1].text == "✅ Не дубль"
    assert possible_duplicate.buttons[1][1].callback_data == "rev:reviewtoken:uniq"
    assert needs_review.buttons[1][0].text == "🚫 Не учитывать"
    assert all(
        button.callback_data != "rev:reviewtoken:dup"
        for row in needs_review.buttons
        for button in row
    )
    assert all(
        button.callback_data != "rev:reviewtoken:uniq"
        for row in needs_review.buttons
        for button in row
    )


def test_review_item_shows_accept_suggestion_when_category_is_suggested() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )

    response = TelegramMainMenuPresenter.show_next_review_item(
        conversation,
        chat_application.ChatReviewQueueItem(
            document_id=uuid4(),
            raw_transaction_id=uuid4(),
            row_index=0,
            status="needs_review",
            account_name="T-Bank Card",
            operation_date=date(2026, 6, 30),
            amount=Decimal("-1250.00"),
            amount_raw=None,
            currency="RUB",
            description="MAGNIT",
            suggested_operation_type="expense",
            normalization_error=None,
            suggested_category_id=uuid4(),
            suggested_category_name="Продукты",
        ),
        action_token="reviewtoken",
    )

    assert response.buttons[0][0].text == "✅ Принять"
    assert response.buttons[0][0].callback_data == "rev:reviewtoken:sug"
    assert response.buttons[0][1].text == "🏷 Категория"
    assert response.buttons[0][1].callback_data == "rev:reviewtoken:conf"
    assert response.buttons[1][0].callback_data == "rev:reviewtoken:trn"


def test_review_category_menu_uses_pages_and_global_category_indexes() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    category_choices = tuple(
        chat_application.ChatReviewCategoryChoice(id=uuid4(), name=f"Категория {index}")
        for index in range(7, 14)
    )

    response = TelegramMainMenuPresenter.show_review_category_menu(
        conversation,
        chat_application.StartedChatReviewCategorySelection(
            action_token="categorytoken",
            item=chat_application.ChatReviewQueueItem(
                document_id=uuid4(),
                raw_transaction_id=uuid4(),
                row_index=0,
                status="needs_review",
                account_name="T-Bank Card",
                operation_date=date(2026, 6, 30),
                amount=Decimal("-1250.00"),
                amount_raw=None,
                currency="RUB",
                description="MAGNIT",
                suggested_operation_type="expense",
                normalization_error=None,
            ),
            category_choices=category_choices,
            page_index=1,
            page_count=3,
            page_start_index=7,
        ),
    )

    assert "Страница 2 из 3" in response.text
    assert response.buttons[0][0].callback_data == "rvc:categorytoken:7"
    assert response.buttons[6][0].callback_data == "rvc:categorytoken:13"
    assert response.buttons[7][0].callback_data == "rcp:categorytoken:0"
    assert response.buttons[7][1].callback_data == "rcp:categorytoken:2"
    assert response.buttons[8][0].text == "🔎 К строке"


def test_review_item_formats_human_readable_status_and_hint() -> None:
    item = chat_application.ChatReviewQueueItem(
        document_id=uuid4(),
        raw_transaction_id=uuid4(),
        row_index=1,
        status="possible_duplicate",
        account_name="T-Bank Card",
        operation_date=date(2026, 6, 30),
        amount=Decimal("-1250.00"),
        amount_raw=None,
        currency="RUB",
        description="MAGNIT",
        suggested_operation_type="expense",
        normalization_error="Same account, date, amount, and currency.",
    )

    text = TelegramMainMenuPresenter.show_next_review_item(
        ChatConversation(
            provider=ChatProviderCode.TELEGRAM,
            external_chat_id="42",
            conversation_type=ChatConversationType.PRIVATE,
        ),
        item,
        action_token="reviewtoken",
    ).text

    assert "⚠️ Статус: возможный дубль" in text
    assert "🧭 Похоже на: расход" in text
    assert "👉 Что сделать: проверь: это дубль или не дубль" in text
    assert "❗ Почему нужно проверить: Same account, date, amount, and currency." in text


def test_chat_manual_amount_parser_accepts_common_russian_money_format() -> None:
    assert chat_application.ChatManualAmountParser.parse_positive_amount("1 250,50") == Decimal(
        "1250.50"
    )
    assert chat_application.ChatManualAmountParser.parse_positive_amount("1250 руб") == Decimal(
        "1250.00"
    )


def test_chat_manual_date_parser_accepts_russian_and_iso_formats() -> None:
    assert chat_application.ChatManualDateParser.parse("30.06.2026") == date(2026, 6, 30)
    assert chat_application.ChatManualDateParser.parse("2026-06-30") == date(2026, 6, 30)


def test_chat_manual_description_cleaner_removes_extra_spacing() -> None:
    assert chat_application.ChatManualDescriptionCleaner.clean("  Обед   с семьей  ") == (
        "Обед с семьей"
    )
    assert chat_application.ChatManualDescriptionCleaner.clean("   ") is None


def test_chat_review_action_mapper_supports_duplicate_action() -> None:
    assert chat_application.ChatReviewActionMapper.to_review_status_action("dup") == "duplicate"
    assert chat_application.ChatReviewActionMapper.to_action_label("dup") == (
        "строка помечена как дубль"
    )


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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_chat_event_service_returns_safe_start_menu() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=conversation,
        actor=None,
        text="/start",
    )

    response = await ChatEventService().receive_inbound_event(event)

    assert response is not None
    assert "👋 Booker Tee" in response.text
    assert "загружать выписки" in response.text
    assert response.buttons[0][0].callback_data == "link:start"
    assert response.buttons[0][1].callback_data == "help:show"


def test_unlinked_account_notice_includes_telegram_id_and_dev_link() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    actor = ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42")

    response = TelegramMainMenuPresenter.show_unlinked_account_notice(conversation, actor)

    assert "Telegram ID для привязки: 42" in response.text
    assert "/chat-integrations/telegram/dev-link?external_user_id=42" in response.text


def test_shared_feed_import_notification_hides_financial_details() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="-100",
        conversation_type=ChatConversationType.GROUP,
    )

    message = ChatImportNotificationFormatter.format_document_uploaded(
        conversation,
        ImportDocumentUploadedNotification(
            workspace_name="Family",
            document_status=UploadedDocumentStatus.REQUIRES_REVIEW,
            review_url="https://booker.example/imports/documents/1/review",
        ),
    )

    assert "Workspace: Family" in message.text
    assert "Загружена выписка" in message.text
    assert "требует проверки" in message.text
    assert "40000" not in message.text
    assert "statement.pdf" not in message.text
    assert message.buttons[0][0].url == "https://booker.example/imports/documents/1/review"


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
    assert "👋 Booker Tee" in str(requests[0][1]["text"])


@pytest.mark.asyncio
async def test_chat_event_service_does_not_expose_financial_data_for_unknown_message() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=conversation,
        actor=None,
        text="balance",
    )

    response = await ChatEventService().receive_inbound_event(event)

    assert response is not None
    assert "баланс" not in response.text.lower()
    assert response.buttons[0][0].callback_data == "main:menu"


@pytest.mark.asyncio
async def test_chat_event_service_returns_bound_menu_for_linked_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=2,
                raw_transactions_needing_attention=3,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    actor = ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42")
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=conversation,
        actor=actor,
        text="/start",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "✅ Booker Tee подключен" in response.text
    assert "🏠 Family" in response.text
    assert "⚠️ К проверке: 5" in response.text
    assert response.buttons[0][0].callback_data == "status:show"
    assert response.buttons[1][0].callback_data == "upload:start"
    assert response.buttons[1][1].callback_data == "manual:start"


@pytest.mark.asyncio
async def test_chat_event_service_adds_review_link_when_public_base_url_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=2,
                raw_transactions_needing_attention=3,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="status:show",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example/"),
    ).receive_inbound_event(event)

    assert response is not None
    assert response.buttons[0][0].text == "🌐 Web"
    assert response.buttons[0][0].url == "https://booker.example/imports"
    assert response.buttons[1][0].callback_data == "review:next"
    assert response.buttons[1][1].callback_data == "status:show"
    assert response.buttons[2][0].callback_data == "main:menu"


@pytest.mark.asyncio
async def test_chat_event_service_returns_private_status_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=1,
                raw_transactions_needing_attention=4,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    actor = ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42")
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=actor,
        callback_data="status:show",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "📊 Статус" in response.text
    assert "📄 Документы: 1" in response.text
    assert "🔎 Проверка: 4" in response.text
    assert response.buttons[0][0].callback_data == "review:next"
    assert response.buttons[0][1].callback_data == "status:show"
    assert response.buttons[1][0].callback_data == "main:menu"


@pytest.mark.asyncio
async def test_chat_event_service_shows_upload_instructions_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=0,
                raw_transactions_needing_attention=0,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="upload:start",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "📎 Загрузка выписки" in response.text
    assert "Отправь PDF или XLSX файлом" in response.text
    assert response.buttons[0][0].callback_data == "main:menu"


@pytest.mark.asyncio
async def test_chat_event_service_shows_manual_operation_entry_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=0,
                raw_transactions_needing_attention=0,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="manual:start",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "➕ Ручная операция" in response.text
    assert response.buttons[0][0].callback_data == "manual:expense"
    assert response.buttons[0][1].callback_data == "manual:income"
    assert response.buttons[1][0].callback_data == "manual:transfer"


@pytest.mark.asyncio
async def test_chat_event_service_starts_manual_expense_account_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=0,
                raw_transactions_needing_attention=0,
            )

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_income_expense(
            self,
            *,
            context: WorkspaceContext,
            operation_type: OperationType,
        ):
            assert context.workspace.id == workspace_id
            assert operation_type == OperationType.EXPENSE
            return chat_application.StartedChatManualAccountSelection(
                action_token="manualtoken",
                operation_type=OperationType.EXPENSE,
                account_choices=(
                    chat_application.ChatManualAccountChoice(name="Cash", currency="RUB"),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="manual:expense",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "💸 Расход" in response.text
    assert "Откуда ушли деньги?" in response.text
    assert response.buttons[0][0].text == "Cash / RUB"
    assert response.buttons[0][0].callback_data == "mna:manualtoken:0"


@pytest.mark.asyncio
async def test_chat_event_service_starts_manual_transfer_source_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=0,
                raw_transactions_needing_attention=0,
            )

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_transfer(self, *, context: WorkspaceContext):
            assert context.workspace.id == workspace_id
            return chat_application.StartedChatManualAccountSelection(
                action_token="manualtoken",
                operation_type=OperationType.TRANSFER,
                account_choices=(
                    chat_application.ChatManualAccountChoice(name="Cash", currency="RUB"),
                    chat_application.ChatManualAccountChoice(name="Card", currency="RUB"),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="manual:transfer",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "🔁 Перевод" in response.text
    assert "Откуда перевести?" in response.text
    assert response.buttons[0][0].callback_data == "mna:manualtoken:0"
    assert response.buttons[1][0].callback_data == "mna:manualtoken:1"


@pytest.mark.asyncio
async def test_chat_event_service_prompts_manual_amount_after_account_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def select_account(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatManualAccountSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "manualtoken"
            assert selection.account_index == 0
            return chat_application.StartedChatManualAmountInput(
                operation_type=OperationType.EXPENSE,
                account_name="Cash",
                currency="RUB",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="mna:manualtoken:0",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Счет: Cash" in response.text
    assert "Напиши сумму" in response.text


@pytest.mark.asyncio
async def test_chat_event_service_shows_manual_date_menu_after_amount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def continue_from_text_input(
            self,
            *,
            context: WorkspaceContext,
            text: str | None,
        ):
            assert context.workspace.id == workspace_id
            assert text == "1 250,50"
            return chat_application.StartedChatManualDateSelection(
                action_token="datetoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                currency="RUB",
                account_name="Cash",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        text="1 250,50",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Когда была операция?" in response.text
    assert "1250.50 RUB" in response.text
    assert response.buttons[0][0].callback_data == "mnd:datetoken:today"
    assert response.buttons[0][1].callback_data == "mnd:datetoken:yesterday"
    assert response.buttons[1][0].callback_data == "mnd:datetoken:custom"


@pytest.mark.asyncio
async def test_chat_event_service_shows_manual_category_menu_after_date_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    groceries_category_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def select_date(
            self,
            *,
            context: WorkspaceContext,
            selection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "datetoken"
            assert selection.date_action == "today"
            return chat_application.StartedChatManualCategorySelection(
                action_token="categorytoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                currency="RUB",
                account_name="Cash",
                category_choices=(
                    chat_application.ChatManualCategoryChoice(id=None, name="Без категории"),
                    chat_application.ChatManualCategoryChoice(
                        id=groceries_category_id,
                        name="Продукты",
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="mnd:datetoken:today",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Выбери категорию" in response.text
    assert response.buttons[0][0].text == "Без категории"
    assert response.buttons[0][0].callback_data == "mnc:categorytoken:0"
    assert response.buttons[1][0].text == "Продукты"
    assert response.buttons[1][0].callback_data == "mnc:categorytoken:1"


@pytest.mark.asyncio
async def test_chat_event_service_prompts_manual_custom_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def select_date(self, *, context: WorkspaceContext, selection):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "datetoken"
            assert selection.date_action == "custom"
            return chat_application.StartedChatManualDateInput(
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                currency="RUB",
                account_name="Cash",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="mnd:datetoken:custom",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Напиши дату" in response.text
    assert "30.06.2026" in response.text


@pytest.mark.asyncio
async def test_chat_event_service_prompts_manual_description_after_category_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def select_category(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatManualCategorySelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "categorytoken"
            assert selection.category_index == 1
            return chat_application.StartedChatManualDescriptionInput(
                action_token="descriptiontoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                operation_date=date(2026, 6, 30),
                account_name="Cash",
                currency="RUB",
                category_name="Продукты",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="mnc:categorytoken:1",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Описание? Можно пропустить." in response.text
    assert "Категория: Продукты" in response.text
    assert response.buttons[0][0].text == "⏭ Пропустить"
    assert response.buttons[0][0].callback_data == "mndsc:descriptiontoken:skip"


@pytest.mark.asyncio
async def test_chat_event_service_confirms_manual_operation_after_skipped_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def skip_description(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatManualDescriptionSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "descriptiontoken"
            assert selection.description_action == "skip"
            return chat_application.ChatManualOperationConfirmation(
                action_token="confirmtoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                operation_date=date(2026, 6, 30),
                account_name="Cash",
                currency="RUB",
                category_name="Продукты",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="mndsc:descriptiontoken:skip",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Проверь запись" in response.text
    assert "Категория: Продукты" in response.text
    assert "Описание:" not in response.text
    assert response.buttons[0][0].callback_data == "mnf:confirmtoken:ok"


@pytest.mark.asyncio
async def test_chat_event_service_confirms_manual_operation_after_description_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def continue_from_text_input(
            self,
            *,
            context: WorkspaceContext,
            text: str | None,
        ):
            assert context.workspace.id == workspace_id
            assert text == "Обед"
            return chat_application.ChatManualOperationConfirmation(
                action_token="confirmtoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                operation_date=date(2026, 6, 30),
                account_name="Cash",
                currency="RUB",
                category_name="Продукты",
                description="Обед",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        text="Обед",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Проверь запись" in response.text
    assert "Описание: Обед" in response.text
    assert response.buttons[0][0].callback_data == "mnf:confirmtoken:ok"


@pytest.mark.asyncio
async def test_chat_event_service_shows_manual_correction_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def select_correction(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatManualCorrectionSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "confirmtoken"
            assert selection.correction_action == "menu"
            confirmation = chat_application.ChatManualOperationConfirmation(
                action_token="confirmtoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                operation_date=date(2026, 6, 30),
                account_name="Cash",
                currency="RUB",
                category_name="Продукты",
            )
            return chat_application.StartedChatManualCorrectionSelection(
                action_token="confirmtoken",
                confirmation=confirmation,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="mned:confirmtoken:menu",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Что исправить?" in response.text
    assert response.buttons[0][0].callback_data == "mned:confirmtoken:amount"
    assert response.buttons[0][1].callback_data == "mned:confirmtoken:date"
    assert response.buttons[1][0].callback_data == "mned:confirmtoken:category"
    assert response.buttons[2][0].callback_data == "mned:confirmtoken:description"


@pytest.mark.asyncio
async def test_chat_event_service_prompts_manual_description_from_correction_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def select_correction(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatManualCorrectionSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "confirmtoken"
            assert selection.correction_action == "description"
            return chat_application.StartedChatManualDescriptionInput(
                action_token="descriptiontoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                operation_date=date(2026, 6, 30),
                account_name="Cash",
                currency="RUB",
                category_name="Продукты",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="mned:confirmtoken:description",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Описание? Можно пропустить." in response.text
    assert response.buttons[0][0].callback_data == "mndsc:descriptiontoken:skip"


@pytest.mark.asyncio
async def test_chat_event_service_records_manual_operation_after_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def confirm(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatManualConfirmationSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "confirmtoken"
            return chat_application.ChatManualOperationResult(
                operation_id=operation_id,
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                currency="RUB",
                operation_date=date(2026, 6, 30),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="mnf:confirmtoken:ok",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "✅ Операция записана" in response.text
    assert "1250.50 RUB" in response.text
    assert response.buttons[0][0].callback_data == "manual:start"


@pytest.mark.asyncio
async def test_chat_event_service_returns_next_review_item_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=1,
                raw_transactions_needing_attention=1,
            )

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_next_review_item(self, _context: WorkspaceContext):
            return chat_application.StartedChatReviewItem(
                action_token="reviewtoken",
                item=chat_application.ChatReviewQueueItem(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    row_index=1,
                    status="needs_review",
                    account_name="T-Bank Card",
                    operation_date=date(2026, 6, 30),
                    amount=Decimal("-1250.00"),
                    amount_raw=None,
                    currency="RUB",
                    description="MAGNIT",
                    suggested_operation_type="expense",
                    normalization_error=None,
                    suggested_category_name="Продукты",
                    document_row_count=100,
                    document_reviewable_count=37,
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(chat_service, "ChatReviewQueueService", FakeChatReviewQueueService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="review:next",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "🔎 Проверка Booker Tee" in response.text
    assert "📍 Строка: 2 из 100" in response.text
    assert "⏳ Осталось проверить: 37" in response.text
    assert "🏦 Счет: T-Bank Card" in response.text
    assert "📅 Дата: 30.06.2026" in response.text
    assert "💵 Сумма: -1250.00 RUB" in response.text
    assert "📝 Описание: MAGNIT" in response.text
    assert "⚠️ Статус: нужно проверить" in response.text
    assert "🧭 Похоже на: расход" in response.text
    assert "💡 Предложение: расход · Продукты" in response.text
    assert "👉 Что сделать: выбери категорию, перевод или не учитывай" in response.text
    assert response.buttons[0][0].text == "🏷 Категория"
    assert response.buttons[0][0].callback_data == "rev:reviewtoken:conf"
    assert response.buttons[0][1].callback_data == "rev:reviewtoken:trn"
    assert response.buttons[1][0].callback_data == "rev:reviewtoken:ign"
    assert response.buttons[2][0].url == (
        f"https://booker.example/imports/documents/{document_id}/review#raw-{raw_transaction_id}"
    )
    assert response.buttons[3][0].callback_data == "rvn:reviewtoken:prev"
    assert response.buttons[3][1].callback_data == "rvn:reviewtoken:next"


@pytest.mark.asyncio
async def test_chat_event_service_navigates_to_next_review_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_adjacent_review_item(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewNavigationSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "reviewtoken"
            assert selection.direction == "next"
            return chat_application.StartedChatReviewItem(
                action_token="nexttoken",
                item=chat_application.ChatReviewQueueItem(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    row_index=1,
                    status="normalized",
                    account_name="T-Bank Card",
                    operation_date=date(2026, 6, 30),
                    amount=Decimal("-500.00"),
                    amount_raw=None,
                    currency="RUB",
                    description="COFFEE",
                    suggested_operation_type="expense",
                    normalization_error=None,
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatReviewQueueService", FakeChatReviewQueueService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rvn:reviewtoken:next",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "COFFEE" in response.text
    assert "📍 Строка: 2" in response.text
    assert response.buttons[3][0].callback_data == "rvn:nexttoken:prev"
    assert response.buttons[3][1].callback_data == "rvn:nexttoken:next"


@pytest.mark.asyncio
async def test_chat_event_service_returns_empty_review_queue_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            return chat_application.ChatPrivateStatus(
                documents_needing_attention=0,
                raw_transactions_needing_attention=0,
            )

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_next_review_item(self, _context: WorkspaceContext):
            return None

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(chat_service, "ChatReviewQueueService", FakeChatReviewQueueService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="review:next",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "нечего проверять" in response.text
    assert response.buttons[0][0].callback_data == "main:menu"


@pytest.mark.asyncio
async def test_chat_event_service_applies_review_action_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    applied_actions: list[str] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewActionService:
        def __init__(self, _session: object) -> None:
            pass

        async def apply_action(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewActionSelection,
        ):
            applied_actions.append(selection.action)
            assert context.workspace.id == workspace_id
            assert selection.action_token == "reviewtoken"
            return chat_application.ChatReviewActionResult(
                action_label="строка игнорируется",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatReviewActionService", FakeChatReviewActionService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rev:reviewtoken:ign",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert applied_actions == ["ign"]
    assert response is not None
    assert "Готово: строка игнорируется" in response.text
    assert response.buttons[0][0].callback_data == "review:next"


@pytest.mark.asyncio
async def test_chat_event_service_accepts_review_suggestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    accepted_tokens: list[str] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_with_suggestion(
            self,
            *,
            context: WorkspaceContext,
            action_token: str,
        ):
            assert context.workspace.id == workspace_id
            accepted_tokens.append(action_token)
            return chat_application.ChatReviewCategoryActionResult(
                action_result=chat_application.ChatReviewActionResult(
                    action_label="операция подтверждена",
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rev:reviewtoken:sug",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert accepted_tokens == ["reviewtoken"]
    assert response is not None
    assert "Готово: операция подтверждена" in response.text
    assert response.buttons[0][0].callback_data == "review:next"


@pytest.mark.asyncio
async def test_chat_event_service_starts_review_transfer_account_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    account_id = uuid4()
    pair_raw_transaction_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewTransferService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def start_transfer_selection(
            self,
            *,
            context: WorkspaceContext,
            action_token: str,
        ):
            assert context.workspace.id == workspace_id
            assert action_token == "reviewtoken"
            return chat_application.StartedChatReviewTransferSelection(
                action_token="transfertoken",
                item=chat_application.ChatReviewQueueItem(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    row_index=0,
                    status="needs_review",
                    account_name="T-Bank Card",
                    operation_date=date(2026, 6, 30),
                    amount=Decimal("-40000.00"),
                    amount_raw=None,
                    currency="RUB",
                    description="Transfer to deposit",
                    suggested_operation_type="expense",
                    normalization_error=None,
                ),
                pair_choices=(
                    chat_application.ChatReviewTransferPairChoice(
                        id=pair_raw_transaction_id,
                        account_name="Deposit",
                        operation_date=date(2026, 6, 30),
                        amount=Decimal("40000.00"),
                        currency="RUB",
                        description="Incoming transfer",
                        day_distance=0,
                    ),
                ),
                account_choices=(
                    chat_application.ChatReviewTransferAccountChoice(
                        id=account_id,
                        name="Deposit",
                        currency="RUB",
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatReviewTransferService", FakeChatReviewTransferService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rev:reviewtoken:trn",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выбери парную строку" in response.text
    assert "📝 Описание: Transfer to deposit" in response.text
    assert response.buttons[0][0].text == "Пара: Deposit / 30.06.2026 / 40000.00 RUB"
    assert response.buttons[0][0].callback_data == "rvx:transfertoken:0"
    assert response.buttons[1][0].text == "Deposit / RUB"
    assert response.buttons[1][0].callback_data == "rvt:transfertoken:0"


@pytest.mark.asyncio
async def test_chat_event_service_confirms_review_item_as_transfer_with_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    selected_accounts: list[int] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewTransferService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_transfer_with_account(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewTransferAccountSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "transfertoken"
            selected_accounts.append(selection.account_index)
            return chat_application.ChatReviewActionResult(
                action_label="перевод подтвержден",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatReviewTransferService", FakeChatReviewTransferService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rvt:transfertoken:1",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_accounts == [1]
    assert response is not None
    assert "Готово: перевод подтвержден" in response.text
    assert response.buttons[0][0].callback_data == "review:next"


@pytest.mark.asyncio
async def test_chat_event_service_confirms_review_item_as_transfer_with_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    selected_pairs: list[int] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewTransferService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_transfer_with_pair(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewTransferPairSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "transfertoken"
            selected_pairs.append(selection.pair_index)
            return chat_application.ChatReviewActionResult(
                action_label="парный перевод подтвержден",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatReviewTransferService", FakeChatReviewTransferService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rvx:transfertoken:1",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_pairs == [1]
    assert response is not None
    assert "Готово: парный перевод подтвержден" in response.text
    assert response.buttons[0][0].callback_data == "review:next"


@pytest.mark.asyncio
async def test_chat_event_service_starts_review_confirmation_category_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    category_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def start_category_selection(
            self,
            *,
            context: WorkspaceContext,
            action_token: str,
        ):
            assert context.workspace.id == workspace_id
            assert action_token == "reviewtoken"
            return chat_application.StartedChatReviewCategorySelection(
                action_token="categorytoken",
                item=chat_application.ChatReviewQueueItem(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    row_index=0,
                    status="needs_review",
                    account_name="T-Bank Card",
                    operation_date=date(2026, 6, 30),
                    amount=Decimal("-1250.00"),
                    amount_raw=None,
                    currency="RUB",
                    description="MAGNIT",
                    suggested_operation_type="expense",
                    normalization_error=None,
                ),
                category_choices=(
                    chat_application.ChatReviewCategoryChoice(
                        id=category_id,
                        name="Продукты",
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rev:reviewtoken:conf",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выбери категорию" in response.text
    assert "📝 Описание: MAGNIT" in response.text
    assert response.buttons[0][0].text == "Продукты"
    assert response.buttons[0][0].callback_data == "rvc:categorytoken:0"


@pytest.mark.asyncio
async def test_chat_event_service_changes_review_category_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def change_category_page(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewCategoryPageSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "categorytoken"
            assert selection.page_index == 1
            return chat_application.StartedChatReviewCategorySelection(
                action_token="categorytoken",
                item=chat_application.ChatReviewQueueItem(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    row_index=0,
                    status="needs_review",
                    account_name="T-Bank Card",
                    operation_date=date(2026, 6, 30),
                    amount=Decimal("-1250.00"),
                    amount_raw=None,
                    currency="RUB",
                    description="MAGNIT",
                    suggested_operation_type="expense",
                    normalization_error=None,
                ),
                category_choices=(
                    chat_application.ChatReviewCategoryChoice(
                        id=uuid4(),
                        name="Транспорт",
                    ),
                ),
                page_index=1,
                page_count=2,
                page_start_index=7,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rcp:categorytoken:1",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Страница 2 из 2" in response.text
    assert response.buttons[0][0].callback_data == "rvc:categorytoken:7"
    assert response.buttons[1][0].callback_data == "rcp:categorytoken:0"


@pytest.mark.asyncio
async def test_chat_event_service_confirms_review_item_with_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    selected_categories: list[int] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_with_category(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewCategorySelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "categorytoken"
            selected_categories.append(selection.category_index)
            return chat_application.ChatReviewCategoryActionResult(
                action_result=chat_application.ChatReviewActionResult(
                    action_label="операция подтверждена",
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rvc:categorytoken:1",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_categories == [1]
    assert response is not None
    assert "Готово: операция подтверждена" in response.text
    assert response.buttons[0][0].callback_data == "review:next"


@pytest.mark.asyncio
async def test_chat_event_service_shows_property_menu_after_category_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    property_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_with_category(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewCategorySelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "categorytoken"
            assert selection.category_index == 0
            return chat_application.ChatReviewCategoryActionResult(
                property_selection=chat_application.StartedChatReviewPropertySelection(
                    action_token="propertytoken",
                    item=chat_application.ChatReviewQueueItem(
                        document_id=document_id,
                        raw_transaction_id=raw_transaction_id,
                        row_index=0,
                        status="needs_review",
                        account_name="T-Bank Card",
                        operation_date=date(2026, 6, 30),
                        amount=Decimal("-1250.00"),
                        amount_raw=None,
                        currency="RUB",
                        description="MAGNIT",
                        suggested_operation_type="expense",
                        normalization_error=None,
                    ),
                    category_name="Ремонт",
                    property_choices=(
                        chat_application.ChatReviewPropertyChoice(
                            id=None,
                            name="Без объекта",
                        ),
                        chat_application.ChatReviewPropertyChoice(
                            id=property_id,
                            name="9 Maya",
                        ),
                    ),
                )
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rvc:categorytoken:0",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выбери объект" in response.text
    assert "Категория: Ремонт" in response.text
    assert response.buttons[0][0].text == "Без объекта"
    assert response.buttons[0][0].callback_data == "rvp:propertytoken:0"
    assert response.buttons[1][0].text == "9 Maya"
    assert response.buttons[1][0].callback_data == "rvp:propertytoken:1"


@pytest.mark.asyncio
async def test_chat_event_service_confirms_review_item_with_property(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    selected_properties: list[int] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_with_property(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewPropertySelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "propertytoken"
            selected_properties.append(selection.property_index)
            return chat_application.ChatReviewActionResult(
                action_label="операция подтверждена",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_service,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="rvp:propertytoken:1",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_properties == [1]
    assert response is not None
    assert "Готово: операция подтверждена" in response.text
    assert response.buttons[0][0].callback_data == "review:next"


@pytest.mark.asyncio
async def test_chat_event_service_hides_private_status_in_group_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(
            self, _context: WorkspaceContext
        ) -> chat_application.ChatPrivateStatus:
            raise AssertionError("group chats must not read private status")

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="-100",
        conversation_type=ChatConversationType.GROUP,
        title="Booker Tee work chat",
    )
    actor = ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42")
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=actor,
        callback_data="status:show",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "только безопасные уведомления" in response.text
    assert "Family" not in response.text
    assert "review: 4" not in response.text


@pytest.mark.asyncio
async def test_chat_event_service_starts_document_upload_for_bound_private_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatDocumentUploadService:
        def __init__(self, _session: object, _settings: Settings, _downloader: object) -> None:
            pass

        async def start_document_upload(self, **kwargs):
            assert kwargs["context"] is context
            assert kwargs["document"].file_id == "file-id"
            return chat_application.StartedChatDocumentUpload(
                action_token="uploadtoken",
                account_choices=(
                    chat_application.ChatAccountChoice(name="T-Bank Card", currency="RUB"),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatDocumentUploadService", FakeChatDocumentUploadService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.DOCUMENT,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        document=ChatDocument(
            file_id="file-id",
            file_name="statement.pdf",
            mime_type="application/pdf",
        ),
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(),
        cast(Any, object()),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выбери счет" in response.text
    assert response.buttons[0][0].text == "T-Bank Card / RUB"
    assert response.buttons[0][0].callback_data == "upl:uploadtoken:0"


@pytest.mark.asyncio
async def test_chat_event_service_completes_document_upload_after_account_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    uploaded_document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatDocumentUploadService:
        def __init__(self, _session: object, _settings: Settings, _downloader: object) -> None:
            pass

        async def complete_document_upload(self, **kwargs):
            assert kwargs == {
                "context": context,
                "action_token": "uploadtoken",
                "account_index": 0,
            }
            return uploaded_document

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatDocumentUploadService", FakeChatDocumentUploadService)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="upl:uploadtoken:0",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
        cast(Any, object()),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выписка загружена" in response.text
    assert "требует проверки" in response.text
    assert response.buttons[0][0].text == "🔎 Проверка"
    assert response.buttons[0][0].callback_data == "review:next"
    assert response.buttons[0][1].callback_data == "status:show"
    assert response.buttons[0][2].text == "🌐 Web"
    assert response.buttons[0][2].url == (
        f"https://booker.example/imports/documents/{uploaded_document.id}/review"
    )


@pytest.mark.asyncio
async def test_chat_event_service_notifies_shared_feed_after_document_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_application.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    uploaded_document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
    )
    notified_documents: list[object] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatDocumentUploadService:
        def __init__(self, _session: object, _settings: Settings, _downloader: object) -> None:
            pass

        async def complete_document_upload(self, **_kwargs):
            return uploaded_document

    class FakeChatSharedFeedNotificationService:
        def __init__(self, **_kwargs) -> None:
            pass

        async def notify_import_document_uploaded(self, **kwargs) -> None:
            assert kwargs["context"] is context
            notified_documents.append(kwargs["document"])

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatDocumentUploadService", FakeChatDocumentUploadService)
    monkeypatch.setattr(
        chat_service,
        "ChatSharedFeedNotificationService",
        FakeChatSharedFeedNotificationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="upl:uploadtoken:0",
    )
    provider = FakeChatProvider()

    await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
        cast(Any, object()),
        provider,
    ).receive_inbound_event(event)

    assert notified_documents == [uploaded_document]


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
    assert "👋 Booker Tee" in str(requests[1][1]["text"])


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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_shared_feed_notification_service_sends_safe_import_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    binding_id = uuid4()
    connection_id = uuid4()
    provider = FakeChatProvider()
    session = SimpleNamespace(commit_count=0)
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4())),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    document = SimpleNamespace(
        id=uuid4(),
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        original_filename="statement.pdf",
    )
    binding = SimpleNamespace(
        id=binding_id,
        workspace_id=workspace_id,
        connection_id=connection_id,
        provider=ChatProviderCode.FAKE,
        external_chat_id="family-chat",
        conversation_type=ChatConversationType.GROUP,
    )

    async def commit() -> None:
        session.commit_count += 1

    session.commit = commit

    class FakeChatIntegrationRepository:
        def __init__(self, _session) -> None:
            self.delivery = None

        async def list_active_shared_feed_bindings(self, **_kwargs):
            return [binding]

        async def get_event_delivery(self, **_kwargs):
            return self.delivery

        async def create_event_delivery(self, **values):
            self.delivery = SimpleNamespace(id=uuid4(), status=None, **values)
            return self.delivery

        async def mark_event_delivery_sent(self, delivery, **_kwargs) -> None:
            delivery.status = "sent"

        async def mark_event_delivery_failed(self, delivery, **kwargs) -> None:
            delivery.status = "failed"
            delivery.error_message = kwargs["error_message"]

    monkeypatch.setattr(
        notification_dispatcher,
        "ChatIntegrationRepository",
        FakeChatIntegrationRepository,
    )

    summary = await ChatSharedFeedNotificationService(
        session=cast(AsyncSession, session),
        settings=Settings(public_base_url="https://booker.example"),
        provider_registry=ChatNotificationProviderRegistry({ChatProviderCode.FAKE: provider}),
    ).notify_import_document_uploaded(
        context=context,
        document=cast(Any, document),
    )

    assert summary.sent_count == 1
    assert summary.failed_count == 0
    assert session.commit_count == 1
    assert provider.sent_messages[0].conversation.external_chat_id == "family-chat"
    assert "Загружена выписка" in provider.sent_messages[0].text
    assert "statement.pdf" not in provider.sent_messages[0].text
    assert provider.sent_messages[0].buttons[0][0].url == (
        f"https://booker.example/imports/documents/{document.id}/review"
    )


@pytest.mark.asyncio
async def test_chat_identity_binder_rejects_user_without_workspace_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSession:
        async def commit(self) -> None:
            raise AssertionError("commit must not be called")

    class FakeChatIntegrationRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def get_active_membership(self, **_kwargs):
            return None

    monkeypatch.setattr(
        chat_application, "ChatIntegrationRepository", FakeChatIntegrationRepository
    )
    monkeypatch.setattr(chat_application, "WorkspaceRepository", FakeWorkspaceRepository)

    binder = chat_application.ChatIdentityBinder(cast(AsyncSession, FakeSession()))

    with pytest.raises(ChatIdentityBindingError):
        await binder.bind_chat_identity(
            BindChatIdentityCommand(
                workspace_id=uuid4(),
                user_id=uuid4(),
                provider=ChatProviderCode.TELEGRAM,
                external_user_id="42",
                display_name="Anna",
            )
        )


@pytest.mark.asyncio
async def test_chat_identity_binder_creates_binding_for_active_workspace_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    workspace_id = uuid4()

    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0
            self.created_binding = None

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeChatIntegrationRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def get_active_identity_binding(self, **_kwargs):
            return None

        async def create_identity_binding(self, **values):
            binding = SimpleNamespace(id=uuid4(), **values)
            self.session.created_binding = binding
            return binding

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def get_active_membership(self, **_kwargs):
            return SimpleNamespace(id=uuid4(), workspace_id=workspace_id, user_id=user_id)

    monkeypatch.setattr(
        chat_application, "ChatIntegrationRepository", FakeChatIntegrationRepository
    )
    monkeypatch.setattr(chat_application, "WorkspaceRepository", FakeWorkspaceRepository)

    session = FakeSession()
    binder = chat_application.ChatIdentityBinder(cast(AsyncSession, session))

    binding = await binder.bind_chat_identity(
        BindChatIdentityCommand(
            workspace_id=workspace_id,
            user_id=user_id,
            provider=ChatProviderCode.TELEGRAM,
            external_user_id="42",
            display_name="Anna",
        )
    )

    assert session.commit_count == 1
    assert binding.workspace_id == workspace_id
    assert binding.user_id == user_id
    assert binding.provider == ChatProviderCode.TELEGRAM
    assert binding.external_user_id == "42"


@pytest.mark.asyncio
async def test_workspace_chat_resolver_rejects_unbound_chat_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChatIntegrationRepository:
        def __init__(self, _session) -> None:
            pass

        async def list_active_identity_bindings_for_external_user(self, **_kwargs):
            return []

    monkeypatch.setattr(
        chat_application, "ChatIntegrationRepository", FakeChatIntegrationRepository
    )

    resolver = chat_application.WorkspaceChatResolver(cast(AsyncSession, object()))
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=None,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        text="/start",
    )

    with pytest.raises(ChatWorkspaceResolutionError):
        await resolver.require_bound_workspace(event)


@pytest.mark.asyncio
async def test_workspace_chat_resolver_returns_workspace_context_for_bound_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    workspace = SimpleNamespace(id=workspace_id, name="Personal")
    membership = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        workspace_id=workspace_id,
        workspace=workspace,
    )
    user = SimpleNamespace(id=user_id, is_active=True)
    binding = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        workspace_id=workspace_id,
        provider=ChatProviderCode.TELEGRAM,
        external_user_id="42",
    )

    class FakeChatIntegrationRepository:
        def __init__(self, _session) -> None:
            pass

        async def list_active_identity_bindings_for_external_user(self, **_kwargs):
            return [binding]

    class FakeUserRepository:
        def __init__(self, _session) -> None:
            pass

        async def get_active(self, requested_user_id):
            assert requested_user_id == user_id
            return user

    class FakeWorkspaceRepository:
        def __init__(self, _session) -> None:
            pass

        async def get_active_membership(self, **kwargs):
            assert kwargs == {"user_id": user_id, "workspace_id": workspace_id}
            return membership

    monkeypatch.setattr(
        chat_application, "ChatIntegrationRepository", FakeChatIntegrationRepository
    )
    monkeypatch.setattr(chat_application, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(chat_application, "WorkspaceRepository", FakeWorkspaceRepository)

    resolver = chat_application.WorkspaceChatResolver(cast(AsyncSession, object()))
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=None,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        text="/start",
    )

    bound_workspace = await resolver.require_bound_workspace(event)

    assert bound_workspace.identity_binding is binding
    assert bound_workspace.context.user is user
    assert bound_workspace.context.workspace is workspace
    assert bound_workspace.context.membership is membership
