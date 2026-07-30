from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.accounts.dependencies import (
    get_account_directory_service,
    get_account_ledger_reader,
    get_imported_operation_review_use_case,
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
    UpdateAccountCommand,
)
from app.features.categories.models import CategoryKind
from app.features.ledger.application.account_ledger import (
    AccountLedgerDetailView,
    AccountLedgerEntryView,
    AccountView,
    CategoryView,
    OperationRefMoneyEntryView,
    OperationRefView,
    PropertyView,
    RawTransactionLinkView,
)
from app.features.ledger.application.imported_operations import (
    UpdateImportedOperationReviewFieldsCommand,
)
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.listing import AccountEntryFilters, LedgerPage, LedgerPagination
from app.features.ledger.schemas.manual import (
    ManualLedgerNamedOptionDto,
    ManualLedgerReferenceOptionsDto,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


class AccountDirectoryServiceStub:
    def __init__(self, directory: AccountDirectoryDto) -> None:
        self.directory = directory
        self.read_calls: list[tuple[UUID, bool]] = []
        self.create_calls: list[tuple[UUID, CreateAccountCommand]] = []
        self.lifecycle_calls: list[tuple[UUID, UUID, bool, bool, datetime]] = []
        self.update_calls: list[tuple[UUID, UUID, UpdateAccountCommand]] = []

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

    async def update(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        command: UpdateAccountCommand,
    ) -> AccountSummaryDto:
        self.update_calls.append((workspace_id, account_id, command))
        return self.directory.items[0].model_copy(
            update={
                "name": command.name,
                "account_type": command.account_type,
                "currency": command.currency,
                "initial_balance": command.initial_balance,
                "updated_at": datetime(2026, 7, 30, 12, 5, tzinfo=UTC),
            }
        )


class AccountLedgerReaderStub:
    def __init__(
        self,
        detail: AccountLedgerDetailView | None,
        *,
        imported_operations: list[OperationRefView | None] | None = None,
    ) -> None:
        self.detail = detail
        self.imported_operations = imported_operations or []
        self.calls: list[tuple[UUID, UUID, AccountEntryFilters, LedgerPagination]] = []
        self.imported_calls: list[tuple[UUID, UUID, UUID | None]] = []

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

    async def get_imported_operation(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
        account_id: UUID | None = None,
    ) -> OperationRefView | None:
        self.imported_calls.append((workspace_id, operation_id, account_id))
        index = min(len(self.imported_calls) - 1, len(self.imported_operations) - 1)
        return self.imported_operations[index] if index >= 0 else None


class ImportedOperationReviewUseCaseStub:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[WorkspaceContext, UpdateImportedOperationReviewFieldsCommand]] = []

    async def update_review_fields(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateImportedOperationReviewFieldsCommand,
    ) -> object:
        self.calls.append((context, command))
        if self.error:
            raise self.error
        return object()


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
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, AccountLedgerReaderStub, AccountReferenceReaderStub, UUID, UUID]:
    context = api_context(role=role)
    account_id = uuid4()
    ledger = AccountLedgerReaderStub(account_detail(account_id) if found else None)
    references = AccountReferenceReaderStub()
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_account_ledger_reader] = lambda: ledger
    app.dependency_overrides[get_manual_ledger_reference_reader] = lambda: references
    return app, ledger, references, context.workspace.workspace.id, account_id


def account_correction_app(
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
    found: bool = True,
    error: Exception | None = None,
) -> tuple[
    FastAPI,
    AccountLedgerReaderStub,
    ImportedOperationReviewUseCaseStub,
    UUID,
    UUID,
    UUID,
    UUID,
]:
    context = api_context(role=role)
    account_id = uuid4()
    operation_id = uuid4()
    category_id = uuid4()
    property_id = uuid4()
    before, committed = imported_operation_versions(
        account_id=account_id,
        operation_id=operation_id,
        category_id=category_id,
        property_id=property_id,
    )
    ledger = AccountLedgerReaderStub(
        None,
        imported_operations=[before, committed] if found else [None],
    )
    use_case = ImportedOperationReviewUseCaseStub(error=error)
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_account_ledger_reader] = lambda: ledger
    app.dependency_overrides[get_imported_operation_review_use_case] = lambda: use_case
    return (
        app,
        ledger,
        use_case,
        context.workspace.workspace.id,
        account_id,
        operation_id,
        category_id,
    )


def account_detail(account_id: UUID) -> AccountLedgerDetailView:
    account = AccountView(
        id=account_id,
        name="Основной",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("10000.00"),
        updated_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
    )
    other_account = AccountView(
        id=uuid4(),
        name="Накопительный",
        type=AccountType.DEPOSIT,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
        updated_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
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


def imported_operation_versions(
    *,
    account_id: UUID,
    operation_id: UUID,
    category_id: UUID,
    property_id: UUID,
) -> tuple[OperationRefView, OperationRefView]:
    account = AccountView(
        id=account_id,
        name="Основной",
        type=AccountType.CARD,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("10000.00"),
        updated_at=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
    )
    common = {
        "id": operation_id,
        "type": OperationType.EXPENSE,
        "status": OperationStatus.CONFIRMED,
        "source": OperationSource.BANK_PDF,
        "operation_date": date(2026, 7, 29),
        "money_entries": [
            OperationRefMoneyEntryView(
                account_id=account_id,
                account=account,
                amount=Decimal("-881.12"),
            )
        ],
        "raw_transactions": [RawTransactionLinkView(id=uuid4(), uploaded_document_id=uuid4())],
    }
    return (
        OperationRefView(
            **common,
            version=3,
            description="Старое описание",
            category=None,
            property=None,
        ),
        OperationRefView(
            **common,
            version=4,
            description="Такси",
            category=CategoryView(
                id=category_id,
                name="Транспорт",
                kind=CategoryKind.EXPENSE,
            ),
            property=PropertyView(id=property_id, name="Квартира"),
        ),
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
