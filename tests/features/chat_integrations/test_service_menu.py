from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.errors import ChatWorkspaceResolutionError
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


def test_unlinked_account_notice_uses_secure_link_page() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    response = TelegramMainMenuPresenter.show_unlinked_account_notice(
        conversation,
        "https://booker.example/app/chat-integrations/telegram/link",
    )

    assert "/link КОД" in response.text
    assert response.buttons[0][0].url == (
        "https://booker.example/app/chat-integrations/telegram/link"
    )


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


async def test_unbound_private_user_can_redeem_telegram_link_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_codes: list[str] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session) -> None:
            pass

        async def require_bound_workspace(self, _event):
            raise ChatWorkspaceResolutionError("not linked")

    class FakeTelegramLinkCodeBinder:
        def __init__(self, _session) -> None:
            pass

        async def bind(self, *, code, actor):
            seen_codes.append(code)
            assert actor.external_user_id == "42"

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "TelegramLinkCodeBinder", FakeTelegramLinkCodeBinder)
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="2",
        event_type=InboundChatEventType.MESSAGE,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        text="/link workspace.secret",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert seen_codes == ["workspace.secret"]
    assert response is not None
    assert "Telegram подключён" in response.text
