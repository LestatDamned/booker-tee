import pytest

from app.features.chat_integrations.presenters import TelegramMainMenuPresenter
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatProviderCode,
    ChatUser,
    InboundChatEvent,
    InboundChatEventType,
)
from app.features.chat_integrations.service import ChatEventService


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
