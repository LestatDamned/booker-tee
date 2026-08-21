from datetime import date
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.workspace import ChatWorkspaceSelection
from app.features.chat_integrations.handlers import dashboard as chat_dashboard_handler
from app.features.chat_integrations.handlers import workspace as chat_workspace_handler
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.use_cases import dashboard as chat_dashboard
from app.features.chat_integrations.use_cases import workspace as chat_workspace
from app.features.workspaces.service import WorkspaceContext

from .chat_test_support import (
    bound_chat_workspace,
    callback_event,
    message_event,
    patch_bound_workspace,
    patch_private_status,
)


async def test_chat_event_service_returns_bound_menu_for_linked_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

    patch_bound_workspace(monkeypatch, bound_workspace)
    patch_private_status(monkeypatch, documents=2, rows=3)

    event = message_event("/start")

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "✅ Booker Tee подключен" in response.text
    assert "🗂️ Family" in response.text
    assert "📄 Документы: 2" in response.text
    assert "🔎 К проверке: 3" in response.text
    assert response.buttons[0][0].callback_data == "summary:show"
    assert response.buttons[1][0].callback_data == "upload:start"
    assert response.buttons[1][1].callback_data == "manual:start"
    assert response.buttons[2][0].callback_data == "balances:show"
    assert response.buttons[2][1].callback_data == "workspace:choose"


async def test_chat_event_service_adds_review_link_when_public_base_url_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

    patch_bound_workspace(monkeypatch, bound_workspace)
    patch_private_status(monkeypatch, documents=2, rows=3)

    event = callback_event("status:show")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example/"),
    ).receive_inbound_event(event)

    assert response is not None
    assert response.buttons[0][0].text == "🌐 Web"
    assert response.buttons[0][0].url == "https://booker.example/imports"
    assert response.buttons[1][0].callback_data == "review:choose"
    assert response.buttons[1][1].callback_data == "status:show"
    assert response.buttons[2][0].callback_data == "workspace:choose"
    assert response.buttons[3][0].callback_data == "main:menu"


async def test_chat_event_service_returns_private_status_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

    patch_bound_workspace(monkeypatch, bound_workspace)
    patch_private_status(monkeypatch, documents=1, rows=4)

    event = callback_event("status:show")

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "📊 Статус" in response.text
    assert "📄 Документы: 1" in response.text
    assert "🔎 Проверка: 4" in response.text
    assert response.buttons[0][0].callback_data == "review:choose"
    assert response.buttons[0][1].callback_data == "status:show"
    assert response.buttons[1][0].callback_data == "workspace:choose"
    assert response.buttons[2][0].callback_data == "main:menu"


async def test_chat_event_service_returns_monthly_summary_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    context = bound_workspace.context
    summary_contexts: list[WorkspaceContext] = []

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

    patch_bound_workspace(monkeypatch, bound_workspace)
    patch_private_status(monkeypatch, documents=0, rows=0)
    monkeypatch.setattr(
        chat_dashboard_handler, "ChatMonthlySummaryReader", FakeChatMonthlySummaryReader
    )

    event = callback_event("summary:show")

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert summary_contexts == [context]
    assert response is not None
    assert "📊 Сводка" in response.text
    assert "Доход: 100.00 RUB" in response.text
    assert "Документы: 1" in response.text
    assert "К проверке: 2" in response.text


async def test_chat_event_service_returns_monthly_summary_for_selected_month(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    requested_months: list[date] = []

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

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_dashboard_handler, "ChatMonthlySummaryReader", FakeChatMonthlySummaryReader
    )

    event = callback_event("sum:2026-06")

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert requested_months == [date(2026, 6, 1)]
    assert response is not None
    assert "Июнь 2026" in response.buttons[0][1].text
    assert "Доход: 200.00 RUB" in response.text


async def test_chat_event_service_returns_category_summary_for_selected_month(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    requested_months: list[date] = []

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

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_dashboard_handler, "ChatMonthlySummaryReader", FakeChatMonthlySummaryReader
    )

    event = callback_event("sumc:2026-06")

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert requested_months == [date(2026, 6, 1)]
    assert response is not None
    assert "🏷 Категории" in response.text
    assert "Продукты: -50.00 RUB" in response.text


async def test_chat_event_service_returns_account_balances_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    context = bound_workspace.context
    balance_contexts: list[WorkspaceContext] = []

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

    patch_bound_workspace(monkeypatch, bound_workspace)
    patch_private_status(monkeypatch, documents=0, rows=0)
    monkeypatch.setattr(
        chat_dashboard_handler, "ChatAccountBalanceReader", FakeChatAccountBalanceReader
    )

    event = callback_event("balances:show")

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert balance_contexts == [context]
    assert response is not None
    assert "💳 Балансы" in response.text
    assert "Карта: 25000.00 RUB" in response.text


async def test_chat_event_service_starts_workspace_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

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

    patch_bound_workspace(monkeypatch, bound_workspace)
    patch_private_status(monkeypatch, documents=0, rows=0)
    monkeypatch.setattr(chat_workspace_handler, "ChatWorkspaceSwitcher", FakeChatWorkspaceSwitcher)

    event = callback_event("workspace:choose")

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "Рабочее пространство" in response.text
    assert response.buttons[0][0].callback_data == "wsp:worktoken:0"
    assert response.buttons[1][0].callback_data == "wsp:worktoken:1"


async def test_chat_event_service_switches_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_workspace_id = uuid4()
    new_workspace_id = uuid4()
    old_bound_workspace = bound_chat_workspace(old_workspace_id)
    new_bound_workspace = bound_chat_workspace(
        new_workspace_id,
        workspace_name="Business",
        user=old_bound_workspace.context.user,
    )
    new_context = new_bound_workspace.context
    selected_indexes: list[int] = []
    status_contexts: list[WorkspaceContext] = []

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

    patch_bound_workspace(monkeypatch, old_bound_workspace)
    monkeypatch.setattr(chat_workspace_handler, "ChatWorkspaceSwitcher", FakeChatWorkspaceSwitcher)
    monkeypatch.setattr(
        chat_workspace_handler, "ChatPrivateStatusReader", FakeChatPrivateStatusReader
    )

    event = callback_event("wsp:worktoken:1")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_indexes == [1]
    assert status_contexts == [new_context]
    assert response is not None
    assert "🗂️ Business" in response.text
    assert "📄 Документы: 1" in response.text
    assert "🔎 К проверке: 2" in response.text
    assert response.callback_notification == "Готово: пространство переключено"
