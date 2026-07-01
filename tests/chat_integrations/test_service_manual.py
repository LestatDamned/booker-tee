from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.actions.manual import (
    ChatManualAccountSelection,
    ChatManualCategorySelection,
    ChatManualConfirmationSelection,
    ChatManualCorrectionSelection,
    ChatManualDescriptionSelection,
)
from app.features.chat_integrations.handlers import manual as chat_manual_handler
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
from app.features.chat_integrations.use_cases.manual import dto as chat_manual_dto
from app.features.ledger.models import OperationType
from app.features.workspaces.service import WorkspaceContext


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
            return chat_manual_dto.StartedChatManualAccountSelection(
                action_token="manualtoken",
                operation_type=OperationType.EXPENSE,
                account_choices=(
                    chat_manual_dto.ChatManualAccountChoice(name="Cash", currency="RUB"),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(
        chat_manual_handler,
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

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_transfer(self, *, context: WorkspaceContext):
            assert context.workspace.id == workspace_id
            return chat_manual_dto.StartedChatManualAccountSelection(
                action_token="manualtoken",
                operation_type=OperationType.TRANSFER,
                account_choices=(
                    chat_manual_dto.ChatManualAccountChoice(name="Cash", currency="RUB"),
                    chat_manual_dto.ChatManualAccountChoice(name="Card", currency="RUB"),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.StartedChatManualAmountInput(
                operation_type=OperationType.EXPENSE,
                account_name="Cash",
                currency="RUB",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.StartedChatManualDateSelection(
                action_token="datetoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                currency="RUB",
                account_name="Cash",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.StartedChatManualCategorySelection(
                action_token="categorytoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                currency="RUB",
                account_name="Cash",
                category_choices=(
                    chat_manual_dto.ChatManualCategoryChoice(id=None, name="Без категории"),
                    chat_manual_dto.ChatManualCategoryChoice(
                        id=groceries_category_id,
                        name="Продукты",
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.StartedChatManualDateInput(
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                currency="RUB",
                account_name="Cash",
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.StartedChatManualDescriptionInput(
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
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.ChatManualOperationConfirmation(
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
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.ChatManualOperationConfirmation(
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
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            confirmation = chat_manual_dto.ChatManualOperationConfirmation(
                action_token="confirmtoken",
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                operation_date=date(2026, 6, 30),
                account_name="Cash",
                currency="RUB",
                category_name="Продукты",
            )
            return chat_manual_dto.StartedChatManualCorrectionSelection(
                action_token="confirmtoken",
                confirmation=confirmation,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.StartedChatManualDescriptionInput(
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
        chat_manual_handler,
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
    bound_workspace = chat_workspace.BoundChatWorkspace(
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
            return chat_manual_dto.ChatManualOperationResult(
                operation_id=operation_id,
                operation_type=OperationType.EXPENSE,
                amount=Decimal("1250.50"),
                currency="RUB",
                operation_date=date(2026, 6, 30),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_manual_handler,
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
