from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.models import AccountType
from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.application.listing import (
    LedgerPage,
    LedgerPagination,
    ManualOperationFilters,
)
from app.features.ledger.errors import LedgerPostingError, OperationVersionConflictError
from app.features.ledger.mapping.dto import (
    AccountView,
    ManualOperationView,
    OperationRefMoneyEntryView,
)
from app.features.ledger.models import OperationStatus, OperationType
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.models import WorkspaceMemberStatus, WorkspaceRole
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.routes import router as manual_ledger_router
from app.web.templating import WEB_STATIC_ROOT


def manual_expense() -> ManualOperationView:
    account = account_view("Карта")
    return ManualOperationView(
        id=uuid4(),
        version=1,
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
        version=1,
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


def valid_edit_form(operation: ManualOperationView) -> dict[str, str]:
    primary_entry = operation.primary_entry
    assert primary_entry is not None
    return {
        "version": str(operation.version),
        "operation_type": operation.type.value,
        "account_id": str(primary_entry.account_id),
        "destination_account_id": "",
        "amount": str(operation.edit_amount),
        "operation_date": operation.operation_date.isoformat(),
        "category_id": "",
        "property_id": "",
        "description": operation.description or "",
        "return_to": "/_next/ledger/manual?page=1&per_page=50",
    }


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


def manual_operation_matches(
    operation: ManualOperationView,
    filters: ManualOperationFilters,
) -> bool:
    if filters.date_from is not None and operation.operation_date < filters.date_from:
        return False
    if filters.date_to is not None and operation.operation_date > filters.date_to:
        return False
    if filters.operation_type is not None and operation.type != filters.operation_type:
        return False
    if filters.status is not None and operation.status != filters.status:
        return False
    operation_account_ids = {
        entry.account_id
        for entry in (
            operation.primary_entry,
            operation.source_entry,
            operation.destination_entry,
        )
        if entry is not None
    }
    if filters.account_id is not None and filters.account_id not in operation_account_ids:
        return False
    if filters.category_id is not None and operation.category_id != filters.category_id:
        return False
    if filters.property_id is not None and operation.property_id != filters.property_id:
        return False
    return not (
        filters.search and filters.search.casefold() not in (operation.description or "").casefold()
    )


class ManualLedgerCalls:
    def __init__(self) -> None:
        self.operations: list[ManualOperationView] = []
        self.categories: list[Any] = []
        self.properties: list[Any] = []
        self.page = LedgerPage(page=1, per_page=50, total=0)
        self.workspace_ids: list[UUID] = []
        self.filters: list[ManualOperationFilters] = []
        self.paginations: list[LedgerPagination] = []
        self.update_commands: list[UpdateManualOperationCommand] = []
        self.income_expense_commands: list[CreateManualIncomeExpenseCommand] = []
        self.transfer_commands: list[CreateManualTransferCommand] = []
        self.updated_workspace_ids: list[UUID] = []
        self.update_error: LedgerPostingError | None = None
        self.lifecycle_error: LedgerPostingError | None = None
        self.cancelled_ids: list[UUID] = []
        self.restored_ids: list[UUID] = []
        self.deleted_ids: list[UUID] = []
        self.refreshed_workspace_ids: list[UUID] = []
        self.realistic_listing = False


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
            if calls.realistic_listing:
                operations = [
                    operation
                    for operation in calls.operations
                    if manual_operation_matches(operation, filters)
                ]
                operations.sort(key=lambda operation: operation.operation_date, reverse=True)
                page = LedgerPage(
                    page=pagination.page,
                    per_page=pagination.per_page,
                    total=len(operations),
                )
                return operations[pagination.offset : pagination.offset + pagination.per_page], page
            return calls.operations, calls.page

        async def get_manual_operation(
            self,
            *,
            workspace_id: UUID,
            operation_id: UUID,
        ) -> ManualOperationView | None:
            calls.workspace_ids.append(workspace_id)
            return next(
                (operation for operation in calls.operations if operation.id == operation_id),
                None,
            )

        async def update_manual_operation(
            self,
            *,
            context: WorkspaceContext,
            command: UpdateManualOperationCommand,
        ) -> Any:
            calls.updated_workspace_ids.append(context.workspace.id)
            calls.update_commands.append(command)
            if calls.update_error is not None:
                raise calls.update_error
            operation = next(
                operation for operation in calls.operations if operation.id == command.operation_id
            )
            if (
                command.expected_version is not None
                and command.expected_version != operation.version
            ):
                raise OperationVersionConflictError()
            updated_operation = replace(
                operation,
                version=operation.version + 1,
                type=command.operation_type,
                operation_date=command.operation_date,
                description=command.description,
                category_id=command.category_id,
                property_id=command.property_id,
                edit_amount=command.amount,
            )
            calls.operations = [
                updated_operation if item.id == updated_operation.id else item
                for item in calls.operations
            ]
            return SimpleNamespace(id=command.operation_id)

        async def create_manual_income_expense(
            self,
            *,
            context: WorkspaceContext,
            command: CreateManualIncomeExpenseCommand,
        ) -> Any:
            calls.updated_workspace_ids.append(context.workspace.id)
            calls.income_expense_commands.append(command)
            if calls.update_error is not None:
                raise calls.update_error
            template = calls.operations[0]
            primary_entry = template.primary_entry
            assert primary_entry is not None
            created_id = uuid4()
            amount = (
                command.amount
                if command.operation_type == OperationType.INCOME
                else -command.amount
            )
            calls.operations.append(
                replace(
                    template,
                    id=created_id,
                    type=command.operation_type,
                    operation_date=command.operation_date,
                    description=command.description,
                    category_id=command.category_id,
                    property_id=command.property_id,
                    primary_entry=replace(primary_entry, amount=amount),
                    edit_amount=command.amount,
                )
            )
            return SimpleNamespace(id=created_id)

        async def create_manual_transfer(
            self,
            *,
            context: WorkspaceContext,
            command: CreateManualTransferCommand,
        ) -> Any:
            calls.updated_workspace_ids.append(context.workspace.id)
            calls.transfer_commands.append(command)
            if calls.update_error is not None:
                raise calls.update_error
            created_id = uuid4()
            return SimpleNamespace(id=created_id)

        async def cancel_manual_operation(
            self,
            *,
            context: WorkspaceContext,
            operation_id: UUID,
        ) -> Any:
            calls.updated_workspace_ids.append(context.workspace.id)
            calls.cancelled_ids.append(operation_id)
            if calls.lifecycle_error is not None:
                raise calls.lifecycle_error
            calls.operations = [
                replace(
                    operation,
                    version=operation.version + 1,
                    status=OperationStatus.IGNORED,
                )
                if operation.id == operation_id
                else operation
                for operation in calls.operations
            ]
            return SimpleNamespace(id=operation_id)

        async def restore_manual_operation(
            self,
            *,
            context: WorkspaceContext,
            operation_id: UUID,
        ) -> Any:
            calls.updated_workspace_ids.append(context.workspace.id)
            calls.restored_ids.append(operation_id)
            if calls.lifecycle_error is not None:
                raise calls.lifecycle_error
            calls.operations = [
                replace(
                    operation,
                    version=operation.version + 1,
                    status=OperationStatus.CONFIRMED,
                )
                if operation.id == operation_id
                else operation
                for operation in calls.operations
            ]
            return SimpleNamespace(id=operation_id)

        async def delete_manual_operation(
            self,
            *,
            context: WorkspaceContext,
            operation_id: UUID,
        ) -> None:
            calls.updated_workspace_ids.append(context.workspace.id)
            calls.deleted_ids.append(operation_id)
            if calls.lifecycle_error is not None:
                raise calls.lifecycle_error
            calls.operations = [
                operation for operation in calls.operations if operation.id != operation_id
            ]

    class FakeAccountService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_active_accounts(self, workspace_id: UUID) -> list[AccountView]:
            calls.workspace_ids.append(workspace_id)
            accounts: dict[UUID, AccountView] = {}
            for operation in calls.operations:
                for entry in (
                    operation.primary_entry,
                    operation.source_entry,
                    operation.destination_entry,
                ):
                    if entry is not None and entry.account is not None:
                        accounts[entry.account.id] = entry.account
            return list(accounts.values())

    class FakeCategoryService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_or_seed_defaults(
            self,
            workspace_id: UUID,
            _workspace_type: Any,
        ) -> list[Any]:
            calls.workspace_ids.append(workspace_id)
            return calls.categories

    class FakePropertyService:
        def __init__(self, _session: AsyncSession) -> None:
            pass

        async def list_active(self, workspace_id: UUID) -> list[Any]:
            calls.workspace_ids.append(workspace_id)
            return calls.properties

    class FakeSession:
        async def refresh(self, instance: Any) -> None:
            calls.refreshed_workspace_ids.append(instance.id)

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield cast(AsyncSession, FakeSession())

    async def context_override(request: Request) -> WorkspaceContext:
        request.state.workspace_context = context
        request.state.csrf_token = "test-csrf-token"
        return context

    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.LedgerPostingService",
        FakeLedgerPostingService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.AccountService",
        FakeAccountService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.CategoryService",
        FakeCategoryService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.routes.PropertyService",
        FakePropertyService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.create_routes.LedgerPostingService",
        FakeLedgerPostingService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.create_routes.AccountService",
        FakeAccountService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.create_routes.CategoryService",
        FakeCategoryService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.create_routes.PropertyService",
        FakePropertyService,
    )
    monkeypatch.setattr(
        "app.web.features.ledger.manual.lifecycle_routes.LedgerPostingService",
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
