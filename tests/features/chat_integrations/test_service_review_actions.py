from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.actions.review import (
    ChatReviewActionConfirmationSelection,
    ChatReviewActionSelection,
)
from app.features.chat_integrations.errors import (
    ChatReviewActionError,
)
from app.features.chat_integrations.handlers import review_actions as chat_review_action_handler
from app.features.chat_integrations.handlers import (
    review_confirmation as chat_review_confirmation_handler,
)
from app.features.chat_integrations.handlers import review_queue as chat_review_queue_handler
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatProviderCode,
    ChatUser,
    InboundChatEvent,
    InboundChatEventType,
)
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.use_cases import (
    workspace as chat_workspace,
)
from app.features.chat_integrations.use_cases.review import (
    dto as chat_review_dto,
)
from app.features.workspaces.service import WorkspaceContext


def _build_chat_review_queue_item(
    *,
    description: str = "NEXT ROW",
    document_id: UUID | None = None,
    raw_transaction_id: UUID | None = None,
) -> chat_review_dto.ChatReviewQueueItem:
    return chat_review_dto.ChatReviewQueueItem(
        document_id=document_id or uuid4(),
        raw_transaction_id=raw_transaction_id or uuid4(),
        row_index=2,
        status="needs_review",
        account_name="T-Bank Card",
        operation_date=date(2026, 6, 30),
        amount=Decimal("-500.00"),
        amount_raw=None,
        currency="RUB",
        description=description,
        suggested_operation_type="expense",
        normalization_error=None,
    )


def _patch_next_review_item_after_action(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workspace_id: UUID,
    item: chat_review_dto.ChatReviewQueueItem | None = None,
) -> None:
    next_item = item or _build_chat_review_queue_item()

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_next_review_item(self, context: WorkspaceContext):
            assert context.workspace.id == workspace_id
            return chat_review_dto.StartedChatReviewItem(
                action_token="nexttoken",
                item=next_item,
            )

    monkeypatch.setattr(
        chat_review_queue_handler, "ChatReviewQueueService", FakeChatReviewQueueService
    )


@pytest.mark.asyncio
async def test_chat_event_service_starts_review_action_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    confirmation_actions: list[str] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewActionService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_action_confirmation(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewActionSelection,
        ):
            confirmation_actions.append(selection.action)
            assert context.workspace.id == workspace_id
            assert selection.action_token == "reviewtoken"
            return chat_review_dto.StartedChatReviewActionConfirmation(
                action_token="confirmtoken",
                item=_build_chat_review_queue_item(description="ROW TO IGNORE"),
                action=selection.action,
                action_label="строка игнорируется",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_action_handler, "ChatReviewActionService", FakeChatReviewActionService
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
        callback_data="rev:reviewtoken:ign",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert confirmation_actions == ["ign"]
    assert response is not None
    assert "Не учитывать строку?" in response.text
    assert "ROW TO IGNORE" in response.text
    assert response.buttons[0][0].callback_data == "rva:confirmtoken"
    assert response.buttons[1][0].callback_data == "rvb:confirmtoken"


@pytest.mark.asyncio
async def test_chat_event_service_shows_friendly_stale_review_button_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
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

    class FakeChatReviewActionService:
        def __init__(self, _session: object) -> None:
            pass

        async def apply_action(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewActionSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "oldtoken"
            raise ChatReviewActionError("This review action expired. Open the next row again.")

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_action_handler, "ChatReviewActionService", FakeChatReviewActionService
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
        callback_data="rev:oldtoken:uniq",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Кнопка устарела" in response.text
    assert "This review action expired" not in response.text
    assert response.buttons[0][0].callback_data == "review:next"
    assert response.buttons[0][1].callback_data == "main:menu"


@pytest.mark.asyncio
async def test_chat_event_service_confirms_review_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    confirmed_tokens: list[str] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewActionService:
        def __init__(self, _session: object) -> None:
            pass

        async def confirm_action(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewActionConfirmationSelection,
        ):
            assert context.workspace.id == workspace_id
            confirmed_tokens.append(selection.action_token)
            return chat_review_dto.ChatReviewActionResult(
                action_label="строка игнорируется",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_action_handler, "ChatReviewActionService", FakeChatReviewActionService
    )
    _patch_next_review_item_after_action(monkeypatch, workspace_id=workspace_id)

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
        callback_data="rva:confirmtoken",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert confirmed_tokens == ["confirmtoken"]
    assert response is not None
    assert "NEXT ROW" in response.text
    assert response.callback_notification == "Готово: строка игнорируется"
    assert response.buttons[0][0].callback_data == "rev:nexttoken:conf"


@pytest.mark.asyncio
async def test_chat_event_service_continues_after_confirmed_review_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    requested_anchors: list[chat_review_dto.ChatReviewContinuationAnchor] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewActionService:
        def __init__(self, _session: object) -> None:
            pass

        async def confirm_action(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewActionConfirmationSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "confirmtoken"
            return chat_review_dto.ChatReviewActionResult(
                action_label="строка игнорируется",
                continuation_anchor=chat_review_dto.ChatReviewContinuationAnchor(
                    document_id=document_id,
                    row_index=14,
                ),
            )

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_next_review_item(self, _context: WorkspaceContext):
            raise AssertionError("Expected continuation after the confirmed row.")

        async def start_next_review_item_after(
            self,
            *,
            context: WorkspaceContext,
            anchor: chat_review_dto.ChatReviewContinuationAnchor,
        ):
            assert context.workspace.id == workspace_id
            requested_anchors.append(anchor)
            return chat_review_dto.StartedChatReviewItem(
                action_token="nexttoken",
                item=_build_chat_review_queue_item(
                    description="ROW 15",
                    document_id=document_id,
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_action_handler, "ChatReviewActionService", FakeChatReviewActionService
    )
    monkeypatch.setattr(
        chat_review_queue_handler, "ChatReviewQueueService", FakeChatReviewQueueService
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
        callback_data="rva:confirmtoken",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert requested_anchors == [
        chat_review_dto.ChatReviewContinuationAnchor(document_id=document_id, row_index=14)
    ]
    assert response is not None
    assert "ROW 15" in response.text


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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_review_dto.ChatReviewCategoryActionResult(
                action_result=chat_review_dto.ChatReviewActionResult(
                    action_label="операция подтверждена",
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_confirmation_handler,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )
    _patch_next_review_item_after_action(monkeypatch, workspace_id=workspace_id)

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
    assert "NEXT ROW" in response.text
    assert response.callback_notification == "Готово: операция подтверждена"
    assert response.buttons[0][0].callback_data == "rev:nexttoken:conf"
