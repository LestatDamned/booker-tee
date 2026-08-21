from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatProviderCode,
    ChatUser,
    InboundChatEvent,
    InboundChatEventType,
)
from app.features.chat_integrations.use_cases.dashboard import ChatPrivateStatus
from app.features.chat_integrations.use_cases.workspace import BoundChatWorkspace
from app.features.workspaces.service import WorkspaceContext


def bound_chat_workspace(
    workspace_id: UUID,
    *,
    workspace_name: str = "Family",
    user: object | None = None,
) -> BoundChatWorkspace:
    return BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=WorkspaceContext(
            user=cast(
                Any,
                user
                if user is not None
                else SimpleNamespace(
                    id=uuid4(), name="Anna", email="anna@example.test"
                ),
            ),
            workspace=cast(
                Any,
                SimpleNamespace(
                    id=workspace_id,
                    name=workspace_name,
                    default_currency="RUB",
                ),
            ),
            membership=cast(Any, SimpleNamespace(id=uuid4())),
        ),
    )


def callback_event(
    callback_data: str,
    *,
    conversation_type: ChatConversationType = ChatConversationType.PRIVATE,
    external_chat_id: str = "42",
    title: str | None = None,
) -> InboundChatEvent:
    return _inbound_event(
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation_type=conversation_type,
        external_chat_id=external_chat_id,
        title=title,
        callback_data=callback_data,
    )


def message_event(text: str) -> InboundChatEvent:
    return _inbound_event(
        event_type=InboundChatEventType.MESSAGE,
        conversation_type=ChatConversationType.PRIVATE,
        external_chat_id="42",
        title=None,
        text=text,
    )


def patch_bound_workspace(
    monkeypatch: pytest.MonkeyPatch,
    bound_workspace: BoundChatWorkspace,
) -> None:
    class WorkspaceChatResolverStub:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    monkeypatch.setattr(
        chat_service,
        "WorkspaceChatResolver",
        WorkspaceChatResolverStub,
    )


def patch_private_status(
    monkeypatch: pytest.MonkeyPatch,
    *,
    documents: int,
    rows: int,
) -> None:
    class ChatPrivateStatusReaderStub:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(self, _context: WorkspaceContext) -> ChatPrivateStatus:
            return ChatPrivateStatus(
                documents_needing_attention=documents,
                raw_transactions_needing_attention=rows,
            )

    monkeypatch.setattr(
        chat_service,
        "ChatPrivateStatusReader",
        ChatPrivateStatusReaderStub,
    )


def _inbound_event(
    *,
    event_type: InboundChatEventType,
    conversation_type: ChatConversationType,
    external_chat_id: str,
    title: str | None,
    callback_data: str | None = None,
    text: str | None = None,
) -> InboundChatEvent:
    return InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=event_type,
        conversation=ChatConversation(
            provider=ChatProviderCode.TELEGRAM,
            external_chat_id=external_chat_id,
            conversation_type=conversation_type,
            title=title,
        ),
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data=callback_data,
        text=text,
    )
