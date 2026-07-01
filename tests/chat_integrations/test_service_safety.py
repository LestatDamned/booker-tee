from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatProviderCode,
    ChatUser,
    InboundChatEvent,
    InboundChatEventType,
)
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.use_cases import dashboard as chat_dashboard
from app.features.chat_integrations.use_cases import workspace as chat_workspace
from app.features.workspaces.service import WorkspaceContext


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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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

        async def read_status(self, _context: WorkspaceContext) -> chat_dashboard.ChatPrivateStatus:
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
