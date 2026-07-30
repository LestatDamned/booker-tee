from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.accounts.dependencies import get_account_directory_service
from app.features.accounts.models import AccountType
from app.features.accounts.schemas import (
    AccountBalanceDirection,
    AccountDirectoryCapabilitiesDto,
    AccountDirectoryDto,
    AccountDirectoryReadonlyReason,
    AccountSummaryDto,
    CreateAccountCommand,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


class AccountDirectoryServiceStub:
    def __init__(self, directory: AccountDirectoryDto) -> None:
        self.directory = directory
        self.read_calls: list[tuple[UUID, bool]] = []
        self.create_calls: list[tuple[UUID, CreateAccountCommand]] = []
        self.lifecycle_calls: list[tuple[UUID, UUID, bool, bool, datetime]] = []

    async def read(
        self,
        *,
        workspace_id: UUID,
        can_create: bool,
    ) -> AccountDirectoryDto:
        self.read_calls.append((workspace_id, can_create))
        return self.directory

    async def create(
        self,
        *,
        workspace_id: UUID,
        command: CreateAccountCommand,
    ) -> AccountSummaryDto:
        self.create_calls.append((workspace_id, command))
        return self.directory.items[0]

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        is_active: bool,
        expected_active: bool,
        expected_updated_at: datetime,
    ) -> AccountSummaryDto:
        self.lifecycle_calls.append(
            (
                workspace_id,
                account_id,
                is_active,
                expected_active,
                expected_updated_at,
            )
        )
        return self.directory.items[0].model_copy(
            update={
                "is_active": is_active,
                "updated_at": datetime(2026, 7, 30, 12, 5, tzinfo=UTC),
            }
        )


def accounts_app(
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, AccountDirectoryServiceStub, UUID]:
    context = api_context(role=role)
    can_create = role in {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.EDITOR,
    }
    service = AccountDirectoryServiceStub(account_directory(can_create=can_create))
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_account_directory_service] = lambda: service
    return app, service, context.workspace.workspace.id


def account_directory(*, can_create: bool = True) -> AccountDirectoryDto:
    return AccountDirectoryDto(
        items=[
            AccountSummaryDto(
                id=uuid4(),
                name="Основной",
                account_type=AccountType.CARD,
                currency="RUB",
                initial_balance=Decimal("10000.00"),
                balance=Decimal("9118.88"),
                balance_direction=AccountBalanceDirection.POSITIVE,
                movement_count=4,
                is_active=True,
                updated_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
            )
        ],
        account_types=list(AccountType),
        capabilities=AccountDirectoryCapabilitiesDto(
            can_create=can_create,
            readonly_reason_code=(
                None if can_create else AccountDirectoryReadonlyReason.FINANCIAL_WRITE_FORBIDDEN
            ),
        ),
    )
