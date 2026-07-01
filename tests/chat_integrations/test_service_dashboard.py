from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.actions.workspace import ChatWorkspaceSelection
from app.features.chat_integrations.handlers import dashboard as chat_dashboard_handler
from app.features.chat_integrations.handlers import workspace as chat_workspace_handler
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
async def test_chat_event_service_returns_bound_menu_for_linked_start(
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
    assert "🗂️ Family" in response.text
    assert "⚠️ К проверке: 5" in response.text
    assert response.buttons[0][0].callback_data == "summary:show"
    assert response.buttons[1][0].callback_data == "upload:start"
    assert response.buttons[1][1].callback_data == "manual:start"
    assert response.buttons[2][0].callback_data == "balances:show"
    assert response.buttons[2][1].callback_data == "workspace:choose"


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
    assert response.buttons[2][0].callback_data == "workspace:choose"
    assert response.buttons[3][0].callback_data == "main:menu"


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
    assert response.buttons[1][0].callback_data == "workspace:choose"
    assert response.buttons[2][0].callback_data == "main:menu"


@pytest.mark.asyncio
async def test_chat_event_service_returns_monthly_summary_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(
            Any,
            SimpleNamespace(id=workspace_id, name="Family", default_currency="RUB"),
        ),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    summary_contexts: list[WorkspaceContext] = []

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

    class FakeChatMonthlySummaryReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_current_month_summary(self, selected_context: WorkspaceContext):
            summary_contexts.append(selected_context)
            return chat_dashboard.ChatMonthlySummary(
                date_from=date(2026, 7, 1),
                date_to=date(2026, 7, 31),
                currency="RUB",
                income=Decimal("100.00"),
                expense=Decimal("40.00"),
                profit=Decimal("60.00"),
                documents_needing_attention=1,
                raw_transactions_needing_attention=2,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(
        chat_dashboard_handler, "ChatMonthlySummaryReader", FakeChatMonthlySummaryReader
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
        callback_data="summary:show",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert summary_contexts == [context]
    assert response is not None
    assert "📊 Сводка" in response.text
    assert "Доход: 100.00 RUB" in response.text
    assert "К проверке: 3" in response.text


@pytest.mark.asyncio
async def test_chat_event_service_returns_monthly_summary_for_selected_month(
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
    requested_months: list[date] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatMonthlySummaryReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_month_summary(
            self,
            *,
            context: WorkspaceContext,
            month_start: date,
        ):
            assert context.workspace.id == workspace_id
            requested_months.append(month_start)
            return chat_dashboard.ChatMonthlySummary(
                date_from=month_start,
                date_to=date(2026, 6, 30),
                currency="RUB",
                income=Decimal("200.00"),
                expense=Decimal("50.00"),
                profit=Decimal("150.00"),
                documents_needing_attention=0,
                raw_transactions_needing_attention=1,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_dashboard_handler, "ChatMonthlySummaryReader", FakeChatMonthlySummaryReader
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
        callback_data="sum:2026-06",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert requested_months == [date(2026, 6, 1)]
    assert response is not None
    assert "Июнь 2026" in response.buttons[0][1].text
    assert "Доход: 200.00 RUB" in response.text


@pytest.mark.asyncio
async def test_chat_event_service_returns_category_summary_for_selected_month(
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
    requested_months: list[date] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatMonthlySummaryReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_category_summary(
            self,
            *,
            context: WorkspaceContext,
            month_start: date,
        ):
            assert context.workspace.id == workspace_id
            requested_months.append(month_start)
            return chat_dashboard.ChatCategorySummary(
                date_from=month_start,
                date_to=date(2026, 6, 30),
                currency="RUB",
                rows=(
                    chat_dashboard.ChatCategorySummaryRow(
                        category_name="Продукты",
                        income=Decimal("0.00"),
                        expense=Decimal("50.00"),
                        profit=Decimal("-50.00"),
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_dashboard_handler, "ChatMonthlySummaryReader", FakeChatMonthlySummaryReader
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
        callback_data="sumc:2026-06",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert requested_months == [date(2026, 6, 1)]
    assert response is not None
    assert "🏷 Категории" in response.text
    assert "Продукты: -50.00 RUB" in response.text


@pytest.mark.asyncio
async def test_chat_event_service_returns_account_balances_for_bound_callback(
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
    balance_contexts: list[WorkspaceContext] = []

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

    class FakeChatAccountBalanceReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_account_balances(self, selected_context: WorkspaceContext):
            balance_contexts.append(selected_context)
            return chat_dashboard.ChatAccountBalances(
                rows=(
                    chat_dashboard.ChatAccountBalanceRow(
                        account_name="Карта",
                        currency="RUB",
                        balance=Decimal("25000.00"),
                    ),
                ),
                totals=(
                    chat_dashboard.ChatCurrencyBalanceTotal(
                        currency="RUB",
                        balance=Decimal("25000.00"),
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(
        chat_dashboard_handler, "ChatAccountBalanceReader", FakeChatAccountBalanceReader
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
        callback_data="balances:show",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert balance_contexts == [context]
    assert response is not None
    assert "💳 Балансы" in response.text
    assert "Карта: 25000.00 RUB" in response.text


@pytest.mark.asyncio
async def test_chat_event_service_starts_workspace_selection(
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

    class FakeChatWorkspaceSwitcher:
        def __init__(self, _session: object) -> None:
            pass

        async def start_workspace_selection(
            self,
            selected_bound_workspace: chat_workspace.BoundChatWorkspace,
        ):
            assert selected_bound_workspace is bound_workspace
            return chat_workspace.StartedChatWorkspaceSelection(
                action_token="worktoken",
                workspace_choices=(
                    chat_workspace.ChatWorkspaceChoice(
                        id=workspace_id,
                        name="Family",
                        is_current=True,
                    ),
                    chat_workspace.ChatWorkspaceChoice(
                        id=uuid4(),
                        name="Business",
                        is_current=False,
                    ),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)
    monkeypatch.setattr(chat_workspace_handler, "ChatWorkspaceSwitcher", FakeChatWorkspaceSwitcher)

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
        callback_data="workspace:choose",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Рабочее пространство" in response.text
    assert response.buttons[0][0].callback_data == "wsp:worktoken:0"
    assert response.buttons[1][0].callback_data == "wsp:worktoken:1"


@pytest.mark.asyncio
async def test_chat_event_service_switches_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_workspace_id = uuid4()
    new_workspace_id = uuid4()
    user_id = uuid4()
    old_context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=user_id, name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=old_workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    new_context = WorkspaceContext(
        user=old_context.user,
        workspace=cast(Any, SimpleNamespace(id=new_workspace_id, name="Business")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    old_bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=old_context,
    )
    new_bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=new_context,
    )
    selected_indexes: list[int] = []
    status_contexts: list[WorkspaceContext] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return old_bound_workspace

    class FakeChatWorkspaceSwitcher:
        def __init__(self, _session: object) -> None:
            pass

        async def select_workspace(
            self,
            *,
            bound_workspace: chat_workspace.BoundChatWorkspace,
            selection: ChatWorkspaceSelection,
        ):
            assert bound_workspace is old_bound_workspace
            selected_indexes.append(selection.workspace_index)
            return chat_workspace.SelectedChatWorkspace(bound_workspace=new_bound_workspace)

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(self, context: WorkspaceContext):
            status_contexts.append(context)
            return chat_dashboard.ChatPrivateStatus(
                documents_needing_attention=1,
                raw_transactions_needing_attention=2,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_workspace_handler, "ChatWorkspaceSwitcher", FakeChatWorkspaceSwitcher)
    monkeypatch.setattr(
        chat_workspace_handler, "ChatPrivateStatusReader", FakeChatPrivateStatusReader
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
        callback_data="wsp:worktoken:1",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_indexes == [1]
    assert status_contexts == [new_context]
    assert response is not None
    assert "🗂️ Business" in response.text
    assert "⚠️ К проверке: 3" in response.text
    assert response.callback_notification == "Готово: пространство переключено"
