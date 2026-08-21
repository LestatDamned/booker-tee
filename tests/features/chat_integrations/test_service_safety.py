from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.schemas import (
    ChatConversationType,
)
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.use_cases import dashboard as chat_dashboard
from app.features.workspaces.service import WorkspaceContext

from .chat_test_support import bound_chat_workspace, callback_event, patch_bound_workspace


async def test_chat_event_service_hides_private_status_in_group_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(self, _context: WorkspaceContext) -> chat_dashboard.ChatPrivateStatus:
            raise AssertionError("group chats must not read private status")

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)

    event = callback_event(
        "status:show",
        conversation_type=ChatConversationType.GROUP,
        external_chat_id="-100",
        title="Booker Tee work chat",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "только безопасные уведомления" in response.text
    assert "Family" not in response.text
    assert "review: 4" not in response.text
