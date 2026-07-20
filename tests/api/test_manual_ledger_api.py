from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.manual_ledger.references import ManualLedgerReferences
from app.api.v1.manual_ledger.router import (
    get_ledger_posting_service,
    get_manual_ledger_reference_reader,
)
from app.features.accounts.models import Account, AccountType
from app.features.categories.models import Category, CategoryKind
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
from app.features.properties.models import Property, PropertyStatus
from app.features.users.models import User
from app.features.workspaces.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


class LedgerPostingServiceStub:
    def __init__(self, operations: list[ManualOperationView]) -> None:
        self.operations = operations
        self.workspace_ids: list[UUID] = []
        self.filters: list[ManualOperationFilters] = []
        self.paginations: list[LedgerPagination] = []

    async def list_manual_operations(
        self,
        workspace_id: UUID,
        filters: ManualOperationFilters,
        pagination: LedgerPagination,
    ) -> tuple[list[ManualOperationView], LedgerPage]:
        self.workspace_ids.append(workspace_id)
        self.filters.append(filters)
        self.paginations.append(pagination)
        return self.operations, LedgerPage(
            page=pagination.page,
            per_page=pagination.per_page,
            total=len(self.operations),
        )


class ManualLedgerReferenceReaderStub:
    def __init__(self) -> None:
        self.workspace_ids: list[UUID] = []
        self.references = ManualLedgerReferences(
            accounts=[],
            categories=[],
            properties=[],
        )

    async def read(self, workspace_id: UUID) -> ManualLedgerReferences:
        self.workspace_ids.append(workspace_id)
        return self.references


def test_manual_ledger_returns_decimal_money_and_explicit_semantics() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, reference_reader, workspace_id = manual_ledger_app([operation])
    reference_reader.references = filter_references(workspace_id)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/manual-ledger?type=expense&status=confirmed"
            f"&search=++Аренда++за++июль++&operation_id={operation.id}"
            "&page=2&per_page=25"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0] == {
        "id": str(operation.id),
        "version": 3,
        "operationDate": "2026-07-20",
        "description": "Аренда за июль",
        "status": "confirmed",
        "money": {
            "amount": "65000.00",
            "currency": "RUB",
            "operationType": "expense",
            "entryDirection": "outflow",
        },
        "account": {
            "id": str(operation.primary_entry.account_id),
            "name": "Основной счёт",
        },
        "sourceAccount": None,
        "destinationAccount": None,
        "category": None,
        "property": None,
        "capabilities": {
            "canEdit": True,
            "canCancel": True,
            "canRestore": False,
            "canDelete": False,
            "readonlyReason": None,
        },
    }
    assert payload["targetOperationId"] == str(operation.id)
    assert payload["filterOptions"] == {
        "accounts": [
            {
                "id": str(reference_reader.references.accounts[0].id),
                "name": "Основной счёт",
                "currency": "RUB",
            }
        ],
        "categories": [
            {
                "id": str(reference_reader.references.categories[0].id),
                "name": "Аренда",
            }
        ],
        "properties": [
            {
                "id": str(reference_reader.references.properties[0].id),
                "name": "Квартира",
            }
        ],
        "perPage": [25, 50, 100, 200],
    }
    assert payload["pagination"]["page"] == 2
    assert service.workspace_ids == [workspace_id]
    assert reference_reader.workspace_ids == [workspace_id]
    assert service.filters[0].operation_type is OperationType.EXPENSE
    assert service.filters[0].status is OperationStatus.CONFIRMED
    assert service.filters[0].search == "Аренда за июль"
    assert service.paginations == [LedgerPagination(page=2, per_page=25)]


def test_manual_ledger_keeps_transfer_separate_from_income_and_expense() -> None:
    operation = manual_operation(OperationType.TRANSFER)
    app, _, _, _ = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.get("/api/v1/manual-ledger")

    money = response.json()["items"][0]["money"]
    assert money["amount"] == "65000.00"
    assert money["operationType"] == "transfer"
    assert money["entryDirection"] == "transfer"


def test_manual_ledger_tolerantly_normalizes_invalid_query_values() -> None:
    app, service, _, _ = manual_ledger_app([])

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/manual-ledger?date_from=wrong&type=wrong&account_id=wrong"
            "&page=wrong&per_page=999&unknown=value"
        )

    assert response.status_code == 200
    assert service.filters[0].date_from is None
    assert service.filters[0].operation_type is None
    assert service.filters[0].account_id is None
    assert service.paginations == [LedgerPagination(page=1, per_page=200)]


def test_manual_ledger_exposes_readonly_capabilities_for_viewer() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, _, _, _ = manual_ledger_app([operation], role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get("/api/v1/manual-ledger")

    payload = response.json()
    assert payload["capabilities"]["canCreate"] is False
    assert "только для просмотра" in payload["capabilities"]["readonlyReason"]
    assert payload["items"][0]["capabilities"] == {
        "canEdit": False,
        "canCancel": False,
        "canRestore": False,
        "canDelete": False,
        "readonlyReason": ("Ручные операции доступны только для просмотра согласно вашей роли."),
    }


def test_manual_ledger_rejects_reversed_date_range() -> None:
    app, service, reference_reader, _ = manual_ledger_app([])

    with TestClient(app) as client:
        response = client.get("/api/v1/manual-ledger?date_from=2026-07-20&date_to=2026-07-01")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"
    assert service.workspace_ids == []
    assert reference_reader.workspace_ids == []


def manual_ledger_app(
    operations: list[ManualOperationView],
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
):
    app = create_app()
    context = api_context(role=role)
    service = LedgerPostingServiceStub(operations)
    reference_reader = ManualLedgerReferenceReaderStub()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_ledger_posting_service] = lambda: service
    app.dependency_overrides[get_manual_ledger_reference_reader] = lambda: reference_reader
    return app, service, reference_reader, context.workspace.workspace.id


def filter_references(workspace_id: UUID) -> ManualLedgerReferences:
    return ManualLedgerReferences(
        accounts=[
            Account(
                id=uuid4(),
                workspace_id=workspace_id,
                name="Основной счёт",
                type=AccountType.CHECKING,
                currency="RUB",
                initial_balance=Decimal("0.00"),
            )
        ],
        categories=[
            Category(
                id=uuid4(),
                workspace_id=workspace_id,
                name="Аренда",
                kind=CategoryKind.INCOME,
                sort_order=100,
            )
        ],
        properties=[
            Property(
                id=uuid4(),
                workspace_id=workspace_id,
                name="Квартира",
                status=PropertyStatus.ACTIVE,
            )
        ],
    )


def api_context(*, role: WorkspaceRole) -> ApiRequestContext:
    user_id = uuid4()
    workspace_id = uuid4()
    user = User(id=user_id, email="max@example.test", name="Max", password_hash="hash")
    workspace = Workspace(
        id=workspace_id,
        owner_id=user_id,
        name="Personal ledger",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )
    membership = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    return ApiRequestContext(
        workspace=WorkspaceContext(
            user=user,
            workspace=workspace,
            membership=membership,
        ),
        csrf_token="csrf-token",
    )


def manual_operation(operation_type: OperationType) -> ManualOperationView:
    source_account = account_view("Основной счёт")
    destination_account = account_view("Накопительный счёт")
    primary_entry = OperationRefMoneyEntryView(
        account_id=source_account.id,
        account=source_account,
        amount=Decimal("-65000.00"),
    )
    is_transfer = operation_type == OperationType.TRANSFER
    return ManualOperationView(
        id=uuid4(),
        version=3,
        type=operation_type,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 7, 20),
        description="Аренда за июль",
        category_id=None,
        property_id=None,
        category=None,
        property=None,
        primary_entry=primary_entry,
        source_entry=primary_entry if is_transfer else None,
        destination_entry=OperationRefMoneyEntryView(
            account_id=destination_account.id,
            account=destination_account,
            amount=Decimal("65000.00"),
        )
        if is_transfer
        else None,
        edit_amount=Decimal("65000.00"),
    )


def account_view(name: str) -> AccountView:
    return AccountView(
        id=uuid4(),
        name=name,
        type=AccountType.CHECKING,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
