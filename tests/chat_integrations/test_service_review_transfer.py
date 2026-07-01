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
    ChatReviewTransferAccountSelection,
    ChatReviewTransferConfirmationSelection,
    ChatReviewTransferPairSelection,
)
from app.features.chat_integrations.handlers import review_queue as chat_review_queue_handler
from app.features.chat_integrations.handlers import review_transfer as chat_review_transfer_handler
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_review_dto.StartedChatReviewTransferSelection(
                action_token="transfertoken",
                item=chat_review_dto.ChatReviewQueueItem(
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
                    chat_review_dto.ChatReviewTransferPairChoice(
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
                    chat_review_dto.ChatReviewTransferAccountChoice(
                        id=account_id,
                        name="Deposit",
                        currency="RUB",
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_transfer_handler, "ChatReviewTransferService", FakeChatReviewTransferService
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
    assert response.buttons[2][0].text == "⬅️ Назад"
    assert response.buttons[2][0].callback_data == "rvb:transfertoken"


@pytest.mark.asyncio
async def test_chat_event_service_starts_transfer_confirmation_with_account(
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
    selected_accounts: list[int] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewTransferService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def start_transfer_confirmation_with_account(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewTransferAccountSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "transfertoken"
            selected_accounts.append(selection.account_index)
            return chat_review_dto.StartedChatReviewTransferConfirmation(
                action_token="confirmtransfertoken",
                item=_build_chat_review_queue_item(description="Transfer to deposit"),
                target_label="Deposit / RUB",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_transfer_handler, "ChatReviewTransferService", FakeChatReviewTransferService
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
        callback_data="rvt:transfertoken:1",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_accounts == [1]
    assert response is not None
    assert "Подтвердить перевод?" in response.text
    assert "Цель: Deposit / RUB" in response.text
    assert "Transfer to deposit" in response.text
    assert response.buttons[0][0].callback_data == "rvy:confirmtransfertoken"
    assert response.buttons[1][0].callback_data == "rev:confirmtransfertoken:trn"


@pytest.mark.asyncio
async def test_chat_event_service_starts_transfer_confirmation_with_pair(
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
    selected_pairs: list[int] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewTransferService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def start_transfer_confirmation_with_pair(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewTransferPairSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "transfertoken"
            selected_pairs.append(selection.pair_index)
            return chat_review_dto.StartedChatReviewTransferConfirmation(
                action_token="confirmtransfertoken",
                item=_build_chat_review_queue_item(description="Transfer from card"),
                target_label="Пара: Deposit / 30.06.2026 / 40000.00 RUB",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_transfer_handler, "ChatReviewTransferService", FakeChatReviewTransferService
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
        callback_data="rvx:transfertoken:1",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_pairs == [1]
    assert response is not None
    assert "Подтвердить перевод?" in response.text
    assert "Цель: Пара: Deposit / 30.06.2026 / 40000.00 RUB" in response.text
    assert "Transfer from card" in response.text
    assert response.buttons[0][0].callback_data == "rvy:confirmtransfertoken"
    assert response.buttons[1][0].callback_data == "rev:confirmtransfertoken:trn"


@pytest.mark.asyncio
async def test_chat_event_service_confirms_review_transfer(
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

    class FakeChatReviewTransferService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_transfer(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewTransferConfirmationSelection,
        ):
            assert context.workspace.id == workspace_id
            confirmed_tokens.append(selection.action_token)
            return chat_review_dto.ChatReviewActionResult(
                action_label="перевод подтвержден",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_review_transfer_handler, "ChatReviewTransferService", FakeChatReviewTransferService
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
        callback_data="rvy:confirmtransfertoken",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert confirmed_tokens == ["confirmtransfertoken"]
    assert response is not None
    assert "NEXT ROW" in response.text
    assert response.callback_notification == "Готово: перевод подтвержден"
    assert response.buttons[0][0].callback_data == "rev:nexttoken:conf"
