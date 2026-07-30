from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.accounts.dependencies import (
    get_account_directory_service,
    get_account_ledger_reader,
)
from app.api.v1.manual_ledger.dependencies import get_manual_ledger_reference_reader
from app.features.accounts.models import AccountType
from app.features.accounts.schemas import (
    AccountBalanceDirection,
    AccountDirectoryCapabilitiesDto,
    AccountDirectoryDto,
    AccountDirectoryReadonlyReason,
    AccountSummaryDto,
    CreateAccountCommand,
)
from app.features.categories.models import CategoryKind
from app.features.ledger.application.account_ledger import (
    AccountLedgerDetailView,
    AccountLedgerEntryView,
    AccountView,
    CategoryView,
    OperationRefMoneyEntryView,
    OperationRefView,
)
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.listing import AccountEntryFilters, LedgerPage, LedgerPagination
from app.features.ledger.schemas.manual import (
    ManualLedgerNamedOptionDto,
    ManualLedgerReferenceOptionsDto,
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


class AccountLedgerReaderStub:
    def __init__(self, detail: AccountLedgerDetailView | None) -> None:
        self.detail = detail
        self.calls: list[tuple[UUID, UUID, AccountEntryFilters, LedgerPagination]] = []

    async def get_detail(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        filters: AccountEntryFilters,
        pagination: LedgerPagination,
    ) -> AccountLedgerDetailView | None:
        self.calls.append((workspace_id, account_id, filters, pagination))
        return self.detail


class AccountReferenceReaderStub:
    def __init__(self) -> None:
        self.workspace_ids: list[UUID] = []
        self.references = ManualLedgerReferenceOptionsDto(
            accounts=[],
            categories=[
                ManualLedgerNamedOptionDto(id=uuid4(), name="Продукты"),
            ],
            properties=[],
        )

    async def read(self, workspace_id: UUID) -> ManualLedgerReferenceOptionsDto:
        self.workspace_ids.append(workspace_id)
        return self.references


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


def account_detail_app(
    *,
    found: bool = True,
) -> tuple[FastAPI, AccountLedgerReaderStub, AccountReferenceReaderStub, UUID, UUID]:
    context = api_context(role=WorkspaceRole.OWNER)
    account_id = uuid4()
    ledger = AccountLedgerReaderStub(account_detail(account_id) if found else None)
    references = AccountReferenceReaderStub()
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_account_ledger_reader] = lambda: ledger
    app.dependency_overrides[get_manual_ledger_reference_reader] = lambda: references
    return app, ledger, references, context.workspace.workspace.id, account_id


def account_detail(account_id: UUID) -> AccountLedgerDetailView:
    account = AccountView(
        id=account_id,
        name="Основной",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("10000.00"),
    )
    other_account = AccountView(
        id=uuid4(),
        name="Накопительный",
        type=AccountType.DEPOSIT,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
    operation_id = uuid4()
    operation = OperationRefView(
        id=operation_id,
        version=3,
        type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        source=OperationSource.MANUAL,
        operation_date=date(2026, 7, 29),
        description="В резерв",
        category=CategoryView(
            id=uuid4(),
            name="Перевод",
            kind=CategoryKind.TRANSFER,
        ),
        property=None,
        money_entries=[
            OperationRefMoneyEntryView(
                account_id=account.id,
                account=account,
                amount=Decimal("-1500.00"),
            ),
            OperationRefMoneyEntryView(
                account_id=other_account.id,
                account=other_account,
                amount=Decimal("1500.00"),
            ),
        ],
        raw_transactions=[],
    )
    return AccountLedgerDetailView(
        account=account,
        balance=Decimal("8500.00"),
        entries=[
            AccountLedgerEntryView(
                operation=operation,
                operation_id=operation_id,
                amount=Decimal("-1500.00"),
                currency="RUB",
            )
        ],
        page=LedgerPage(page=1, per_page=25, total=1),
    )


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
