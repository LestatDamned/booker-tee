from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.models import AccountType
from app.features.ledger.application.listing import (
    LedgerPage,
    LedgerPagination,
    ManualOperationFilters,
)
from app.features.ledger.mapping.dto import (
    AccountView,
    ManualOperationView,
    OperationRefMoneyEntryView,
)
from app.features.ledger.models import OperationStatus, OperationType
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.models import WorkspaceMemberStatus, WorkspaceRole
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.presenter import ManualLedgerPresenter
from app.web.features.ledger.manual.routes import router as manual_ledger_router
from app.web.templating import WEB_STATIC_ROOT
from app.web.ui.actions import LinkActionVM


def test_presenter_builds_server_owned_financial_and_action_contracts() -> None:
    operation = manual_expense()

    page = ManualLedgerPresenter().present(
        workspace_name="Дом",
        operations=[operation],
        page=LedgerPage(page=1, per_page=50, total=1),
        filters=ManualOperationFilters(),
        focused_operation_id=operation.id,
        can_write=True,
    )

    row = page.rows[0]
    assert row.id == f"next-operation-{operation.id}"
    assert row.money is not None
    assert row.money.amount_label == "350,00"
    assert row.money.operation_type == "expense"
    assert row.money.entry_direction == "outflow"
    assert row.status_label == "подтверждено"
    assert row.is_targeted is True
    assert isinstance(row.actions.primary, LinkActionVM)
    assert row.actions.primary.url.endswith(f"#operation-{operation.id}")
    assert page.filters.active is False
    assert page.total_label == "1 ручная операция"


def test_presenter_keeps_transfer_separate_from_profit() -> None:
    operation = manual_transfer()

    page = ManualLedgerPresenter().present(
        workspace_name="Дом",
        operations=[operation],
        page=LedgerPage(page=1, per_page=50, total=1),
        filters=ManualOperationFilters(),
        focused_operation_id=None,
        can_write=False,
    )

    row = page.rows[0]
    assert row.money is not None
    assert row.money.operation_type == "transfer"
    assert row.money.entry_direction is None
    assert row.operation_tone == "transfer"
    assert [meta.label for meta in row.meta] == ["Карта → Наличные"]
    assert row.actions.primary is None
    assert row.actions.secondary


def test_readonly_route_lists_real_workspace_data_and_preserves_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operations = [operation]
    calls.page = LedgerPage(page=2, per_page=25, total=30)

    with TestClient(app) as client:
        response = client.get(
            f"/_next/ledger/manual?type=expense&status=confirmed&search=coffee"
            f"&operation_id={operation.id}&page=2&per_page=25"
        )

    assert response.status_code == 200
    assert "Frontend Next доступен только для просмотра" in response.text
    assert f'id="next-operation-{operation.id}"' in response.text
    assert "workbench-row--target" in response.text
    assert "money-value--expense" in response.text
    assert "src/app/static/css/app.css" not in response.text
    assert "financial-row" not in response.text
    assert 'option value="expense" selected' in response.text
    assert calls.workspace_ids == [context.workspace.id]
    assert calls.filters[0].operation_type is OperationType.EXPENSE
    assert calls.filters[0].status is OperationStatus.CONFIRMED
    assert calls.filters[0].search == "coffee"
    assert calls.paginations == [LedgerPagination(page=2, per_page=25)]


def test_route_is_readable_for_viewer_but_hides_write_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.VIEWER)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    calls.operations = [manual_expense()]

    with TestClient(app) as client:
        response = client.get("/_next/ledger/manual")

    assert response.status_code == 200
    assert "согласно вашей роли" in response.text
    assert "Изменить в текущем интерфейсе" not in response.text
    assert "Открыть текущую версию" in response.text


def test_transfer_row_uses_financial_badge_and_correct_text_hierarchy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = manual_ledger_app(monkeypatch, context=context)
    operation = manual_transfer()
    calls.operations = [operation]
    calls.page = LedgerPage(page=1, per_page=50, total=1)

    with TestClient(app) as client:
        response = client.get("/_next/ledger/manual")

    assert response.status_code == 200
    assert '<p class="workbench-row__title">17.07.2026</p>' in response.text
    assert '<p class="workbench-row__description">Снятие наличных</p>' in response.text
    assert "ui-badge--transfer" in response.text
    assert "не влияет на прибыль" not in response.text


def test_route_rejects_inactive_workspace_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(
        role=WorkspaceRole.VIEWER,
        status=WorkspaceMemberStatus.DISABLED,
    )
    app, _calls = manual_ledger_app(monkeypatch, context=context)

    with TestClient(app) as client:
        response = client.get("/_next/ledger/manual")

    assert response.status_code == 403


def test_empty_filtered_page_gives_recovery_action(monkeypatch: pytest.MonkeyPatch) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, _calls = manual_ledger_app(monkeypatch, context=context)

    with TestClient(app) as client:
        response = client.get("/_next/ledger/manual?search=missing")

    assert response.status_code == 200
    assert "По этим фильтрам операций нет" in response.text
    assert "Сбросить фильтры" in response.text


def manual_expense() -> ManualOperationView:
    account = account_view("Карта")
    return ManualOperationView(
        id=uuid4(),
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 7, 17),
        description="Кофе",
        category_id=None,
        property_id=None,
        category=None,
        property=None,
        primary_entry=OperationRefMoneyEntryView(
            account_id=account.id,
            account=account,
            amount=Decimal("-350.00"),
        ),
        source_entry=None,
        destination_entry=None,
        edit_amount=Decimal("350.00"),
    )


def manual_transfer() -> ManualOperationView:
    source = account_view("Карта")
    destination = account_view("Наличные")
    return ManualOperationView(
        id=uuid4(),
        type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 7, 17),
        description="Снятие наличных",
        category_id=None,
        property_id=None,
        category=None,
        property=None,
        primary_entry=OperationRefMoneyEntryView(
            account_id=source.id,
            account=source,
            amount=Decimal("-5000.00"),
        ),
        source_entry=OperationRefMoneyEntryView(
            account_id=source.id,
            account=source,
            amount=Decimal("-5000.00"),
        ),
        destination_entry=OperationRefMoneyEntryView(
            account_id=destination.id,
            account=destination,
            amount=Decimal("5000.00"),
        ),
        edit_amount=Decimal("5000.00"),
    )


def account_view(name: str) -> AccountView:
    return AccountView(
        id=uuid4(),
        name=name,
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )


def workspace_context(
    *,
    role: WorkspaceRole,
    status: WorkspaceMemberStatus = WorkspaceMemberStatus.ACTIVE,
) -> WorkspaceContext:
    return cast(
        WorkspaceContext,
        SimpleNamespace(
            user=SimpleNamespace(id=uuid4(), email="user@example.com", is_active=True),
            workspace=SimpleNamespace(id=uuid4(), name="Дом", type="personal", is_active=True),
            membership=SimpleNamespace(role=role, status=status),
        ),
    )


class ManualLedgerCalls:
    def __init__(self) -> None:
        self.operations: list[ManualOperationView] = []
        self.page = LedgerPage(page=1, per_page=50, total=0)
        self.workspace_ids: list[UUID] = []
        self.filters: list[ManualOperationFilters] = []
        self.paginations: list[LedgerPagination] = []


def manual_ledger_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    context: WorkspaceContext,
) -> tuple[FastAPI, ManualLedgerCalls]:
    calls = ManualLedgerCalls()

    class FakeLedgerPostingService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_manual_operations(
            self,
            workspace_id: UUID,
            *,
            filters: ManualOperationFilters,
            pagination: LedgerPagination,
        ) -> tuple[list[ManualOperationView], LedgerPage]:
            calls.workspace_ids.append(workspace_id)
            calls.filters.append(filters)
            calls.paginations.append(pagination)
            return calls.operations, calls.page

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, object())

    async def context_override(request: Request) -> WorkspaceContext:
        request.state.workspace_context = context
        request.state.csrf_token = None
        return context

    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.LedgerPostingService",
        FakeLedgerPostingService,
    )
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="src/app/static"), name="static")
    app.mount("/_next/static", StaticFiles(directory=WEB_STATIC_ROOT), name="web_static")
    app.include_router(manual_ledger_router)
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: Settings(environment="test")
    app.dependency_overrides[get_current_workspace_context] = context_override
    return app, calls
