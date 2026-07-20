from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
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
from app.features.ledger.application.listing import LedgerPage, ManualOperationFilters
from app.features.ledger.mapping.dto import (
    AccountView,
    ManualOperationView,
    OperationRefMoneyEntryView,
)
from app.features.ledger.models import OperationStatus, OperationType
from app.features.ledger.presentation.manual_operations.presenter import ManualOperationsPresenter
from app.features.ledger.router import router as ledger_router
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    require_financial_write_context,
)
from app.features.workspaces.models import WorkspaceMemberStatus, WorkspaceRole
from app.features.workspaces.service import WorkspaceContext


def test_financial_meaning_and_target_state_are_prepared_by_server() -> None:
    operation = manual_expense()

    page = ManualOperationsPresenter().build_page(
        operations=[operation],
        page=LedgerPage(page=1, per_page=50, total=1),
        filters=ManualOperationFilters(),
        focused_operation_id=operation.id,
        can_write=True,
    )

    row = page.rows[0]
    assert row.operation_type is OperationType.EXPENSE
    assert row.amount == Decimal("350.00")
    assert row.amount_direction == "expense"
    assert row.currency == "RUB"
    assert row.id == f"operation-{operation.id}"
    assert row.is_targeted is True


def test_historical_get_preserves_query_when_redirecting_to_react(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.VIEWER)
    app, calls = baseline_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operation = operation

    with TestClient(app) as client:
        response = client.get(
            f"/ledger/manual?operation_id={operation.id}",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == f"/app/ledger/manual?operation_id={operation.id}"
    assert calls.workspace_ids == []


def test_edit_panel_is_loaded_lazily_for_writer(monkeypatch: pytest.MonkeyPatch) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = baseline_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operation = operation

    with TestClient(app) as client:
        panel_response = client.get(f"/ledger/manual/{operation.id}/edit")

    assert panel_response.status_code == 200
    assert "manual-operation-edit-panel-content" in panel_response.text
    assert f'id="manual-operation-form-{operation.id}"' in panel_response.text
    assert "<html" not in panel_response.text


def test_update_has_http_redirect_and_htmx_row_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = workspace_context(role=WorkspaceRole.EDITOR)
    app, calls = baseline_app(monkeypatch, context=context)
    operation = manual_expense()
    calls.operation = operation
    primary_entry = operation.primary_entry
    assert primary_entry is not None
    form = {
        "operation_type": "expense",
        "account_id": str(primary_entry.account_id),
        "amount": "350.00",
        "operation_date": "15.06.2026",
        "description": "Кофе",
    }

    with TestClient(app) as client:
        fallback = client.post(
            f"/ledger/manual/{operation.id}",
            data=form,
            follow_redirects=False,
        )
        htmx = client.post(
            f"/ledger/manual/{operation.id}",
            data=form,
            headers={"HX-Request": "true"},
        )

    anchor = f"/app/ledger/manual?operation_id={operation.id}#operation-{operation.id}"
    assert fallback.status_code == 303
    assert fallback.headers["location"] == anchor
    assert htmx.status_code == 200
    assert f'id="operation-{operation.id}"' in htmx.text
    assert "<html" not in htmx.text
    assert calls.updated_workspace_ids == [context.workspace.id, context.workspace.id]


def manual_expense() -> ManualOperationView:
    account = AccountView(
        id=uuid4(),
        name="Карта",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    return ManualOperationView(
        id=uuid4(),
        version=1,
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 6, 15),
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


def workspace_context(*, role: WorkspaceRole) -> WorkspaceContext:
    return cast(
        WorkspaceContext,
        SimpleNamespace(
            user=SimpleNamespace(id=uuid4(), email="user@example.com", is_active=True),
            workspace=SimpleNamespace(
                id=uuid4(),
                name="Personal",
                type="personal",
                is_active=True,
            ),
            membership=SimpleNamespace(
                role=role,
                status=WorkspaceMemberStatus.ACTIVE,
            ),
        ),
    )


class BaselineCalls:
    def __init__(self) -> None:
        self.operation = manual_expense()
        self.workspace_ids: list[UUID] = []
        self.updated_workspace_ids: list[UUID] = []


def baseline_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    context: WorkspaceContext,
) -> tuple[FastAPI, BaselineCalls]:
    calls = BaselineCalls()

    class FakeAccountService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_active_accounts(self, workspace_id: UUID) -> list[AccountView]:
            calls.workspace_ids.append(workspace_id)
            entry = calls.operation.primary_entry
            return [entry.account] if entry is not None and entry.account is not None else []

    class FakeCategoryService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_or_seed_defaults(
            self,
            workspace_id: UUID,
            _workspace_type: Any,
        ) -> list[Any]:
            calls.workspace_ids.append(workspace_id)
            return []

    class FakePropertyService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_active(self, workspace_id: UUID) -> list[Any]:
            calls.workspace_ids.append(workspace_id)
            return []

    class FakeLedgerPostingService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_manual_operations(
            self,
            workspace_id: UUID,
            **_kwargs: Any,
        ) -> tuple[Any, Any]:
            calls.workspace_ids.append(workspace_id)
            return [calls.operation], LedgerPage(page=1, per_page=50, total=1)

        async def get_manual_operation(
            self,
            *,
            workspace_id: UUID,
            operation_id: UUID,
        ) -> ManualOperationView | None:
            calls.workspace_ids.append(workspace_id)
            return calls.operation if operation_id == calls.operation.id else None

        async def update_manual_operation(self, *, context: WorkspaceContext, command: Any) -> Any:
            calls.updated_workspace_ids.append(context.workspace.id)
            assert command.operation_id == calls.operation.id
            return SimpleNamespace(id=command.operation_id)

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, object())

    async def context_override(request: Request) -> WorkspaceContext:
        request.state.workspace_context = context
        request.state.csrf_token = None
        return context

    monkeypatch.setattr("app.features.ledger.router.AccountService", FakeAccountService)
    monkeypatch.setattr("app.features.ledger.router.CategoryService", FakeCategoryService)
    monkeypatch.setattr("app.features.ledger.router.PropertyService", FakePropertyService)
    monkeypatch.setattr(
        "app.features.ledger.router.LedgerPostingService",
        FakeLedgerPostingService,
    )

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="src/app/static"), name="static")
    app.include_router(ledger_router)
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_settings] = lambda: Settings()
    app.dependency_overrides[get_current_workspace_context] = context_override
    app.dependency_overrides[require_financial_write_context] = context_override
    return app, calls
