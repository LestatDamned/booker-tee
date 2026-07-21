from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.actions.review import (
    ChatReviewDocumentSelection,
    ChatReviewNavigationSelection,
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
from app.features.chat_integrations.use_cases import dashboard as chat_dashboard
from app.features.chat_integrations.use_cases import workspace as chat_workspace
from app.features.chat_integrations.use_cases.review import dto as chat_review_dto
from app.features.workspaces.service import WorkspaceContext


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
            return chat_dashboard.ChatPrivateStatus(
                documents_needing_attention=1,
                raw_transactions_needing_attention=1,
            )

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_next_review_item(self, _context: WorkspaceContext):
            return chat_review_dto.StartedChatReviewItem(
                action_token="reviewtoken",
                item=chat_review_dto.ChatReviewQueueItem(
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
        f"https://booker.example/app/imports/documents/{document_id}/review#raw-{raw_transaction_id}"
    )
    assert response.buttons[3][0].callback_data == "rvn:reviewtoken:prev"
    assert response.buttons[3][1].callback_data == "rvn:reviewtoken:next"
    assert response.buttons[4][0].callback_data == "review:choose"


@pytest.mark.asyncio
async def test_chat_event_service_shows_review_document_selection(
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

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_document_selection(self, selected_context: WorkspaceContext):
            assert selected_context.workspace.id == workspace_id
            return chat_review_dto.StartedChatReviewDocumentSelection(
                action_token="documenttoken",
                document_choices=(
                    chat_review_dto.ChatReviewDocumentChoice(
                        id=document_id,
                        label="june.pdf (T-Bank / card)",
                        reviewable_count=3,
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
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
        callback_data="review:choose",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Проверка выписки" in response.text
    assert "june.pdf (T-Bank / card) - к проверке: 3" in response.text
    assert response.buttons[0][0].callback_data == "rvd:documenttoken:0"


@pytest.mark.asyncio
async def test_chat_event_service_starts_selected_review_document(
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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

        async def start_selected_document_review_item(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewDocumentSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "documenttoken"
            assert selection.document_index == 0
            return chat_review_dto.StartedChatReviewItem(
                action_token="reviewtoken",
                item=chat_review_dto.ChatReviewQueueItem(
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
                    document_label="june.pdf (T-Bank / card)",
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
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
        callback_data="rvd:documenttoken:0",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "📄 Выписка: june.pdf (T-Bank / card)" in response.text
    assert "📝 Описание: MAGNIT" in response.text


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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_review_dto.StartedChatReviewItem(
                action_token="nexttoken",
                item=chat_review_dto.ChatReviewQueueItem(
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
            return chat_dashboard.ChatPrivateStatus(
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
        callback_data="review:next",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "нет строк для проверки" in response.text
    assert response.buttons[0][0].callback_data == "main:menu"
