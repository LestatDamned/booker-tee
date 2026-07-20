from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
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
from app.features.ledger.errors import (
    LedgerPostingError,
    ManualOperationLifecycleConflictError,
    OperationIdempotencyConflictError,
    OperationVersionConflictError,
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
        self.income_commands: list[CreateManualIncomeExpenseCommand] = []
        self.transfer_commands: list[CreateManualTransferCommand] = []
        self.update_commands: list[UpdateManualOperationCommand] = []
        self.lifecycle_calls: list[tuple[str, UUID, int | None]] = []
        self.create_error: LedgerPostingError | None = None
        self.update_error: LedgerPostingError | None = None
        self.lifecycle_error: LedgerPostingError | None = None

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

    async def create_manual_income_expense(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualIncomeExpenseCommand,
    ) -> SimpleNamespace:
        if self.create_error is not None:
            raise self.create_error
        self.workspace_ids.append(context.workspace.id)
        self.income_commands.append(command)
        return SimpleNamespace(id=self.operations[-1].id)

    async def create_manual_transfer(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualTransferCommand,
    ) -> SimpleNamespace:
        if self.create_error is not None:
            raise self.create_error
        self.workspace_ids.append(context.workspace.id)
        self.transfer_commands.append(command)
        return SimpleNamespace(id=self.operations[-1].id)

    async def get_manual_operation(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> ManualOperationView | None:
        self.workspace_ids.append(workspace_id)
        return next(
            (operation for operation in self.operations if operation.id == operation_id),
            None,
        )

    async def update_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateManualOperationCommand,
    ) -> SimpleNamespace:
        if self.update_error is not None:
            raise self.update_error
        self.workspace_ids.append(context.workspace.id)
        self.update_commands.append(command)
        return SimpleNamespace(id=command.operation_id)

    async def cancel_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int | None = None,
    ) -> SimpleNamespace:
        return self._change_status(
            action="cancel",
            context=context,
            operation_id=operation_id,
            expected_version=expected_version,
            status=OperationStatus.IGNORED,
        )

    async def restore_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int | None = None,
    ) -> SimpleNamespace:
        return self._change_status(
            action="restore",
            context=context,
            operation_id=operation_id,
            expected_version=expected_version,
            status=OperationStatus.CONFIRMED,
        )

    async def delete_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int | None = None,
    ) -> None:
        if self.lifecycle_error is not None:
            raise self.lifecycle_error
        self.workspace_ids.append(context.workspace.id)
        self.lifecycle_calls.append(("delete", operation_id, expected_version))
        self.operations = [
            operation for operation in self.operations if operation.id != operation_id
        ]

    def _change_status(
        self,
        *,
        action: str,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int | None,
        status: OperationStatus,
    ) -> SimpleNamespace:
        if self.lifecycle_error is not None:
            raise self.lifecycle_error
        self.workspace_ids.append(context.workspace.id)
        self.lifecycle_calls.append((action, operation_id, expected_version))
        self.operations = [
            replace(operation, status=status, version=operation.version + 1)
            if operation.id == operation_id
            else operation
            for operation in self.operations
        ]
        return SimpleNamespace(id=operation_id)


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
            "id": str(primary_account_id(operation)),
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


def test_manual_operation_edit_loads_fresh_snapshot_and_references() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, reference_reader, workspace_id = manual_ledger_app([operation])
    reference_reader.references = filter_references(workspace_id)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/manual-ledger/{operation.id}/edit")

    assert response.status_code == 200
    assert response.json()["operation"]["id"] == str(operation.id)
    assert response.json()["operation"]["version"] == 3
    assert response.json()["filterOptions"]["accounts"][0]["currency"] == "RUB"
    assert service.workspace_ids == [workspace_id]
    assert reference_reader.workspace_ids == [workspace_id]


def test_manual_operation_edit_requires_write_permission() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, reference_reader, _ = manual_ledger_app(
        [operation],
        role=WorkspaceRole.VIEWER,
    )

    with TestClient(app) as client:
        response = client.get(f"/api/v1/manual-ledger/{operation.id}/edit")

    assert response.status_code == 403
    assert service.workspace_ids == []
    assert reference_reader.workspace_ids == []


def test_manual_income_create_dispatches_workspace_scoped_command() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, workspace_id = manual_ledger_app([operation])
    idempotency_key = uuid4()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            headers={"Idempotency-Key": str(idempotency_key)},
            json={
                "operationType": "income",
                "accountId": str(primary_account_id(operation)),
                "amount": "1250,50",
                "operationDate": "2026-07-20",
                "description": "  Проценты по вкладу  ",
                "categoryId": None,
                "propertyId": None,
            },
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(operation.id)
    assert response.json()["money"]["operationType"] == "income"
    assert service.workspace_ids == [workspace_id, workspace_id]
    assert service.income_commands == [
        CreateManualIncomeExpenseCommand(
            operation_type=OperationType.INCOME,
            account_id=primary_account_id(operation),
            amount=Decimal("1250.50"),
            operation_date=date(2026, 7, 20),
            description="  Проценты по вкладу  ",
            category_id=None,
            property_id=None,
            idempotency_key=idempotency_key,
        )
    ]


def test_manual_expense_create_preserves_expense_semantics() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, workspace_id = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operationType": "expense",
                "accountId": str(primary_account_id(operation)),
                "amount": "881.12",
                "operationDate": "2026-07-21",
                "description": "Коммунальные услуги",
            },
        )

    assert response.status_code == 201
    assert response.json()["money"] == {
        "amount": "65000.00",
        "currency": "RUB",
        "operationType": "expense",
        "entryDirection": "outflow",
    }
    assert service.workspace_ids == [workspace_id, workspace_id]
    assert service.income_commands[0].operation_type is OperationType.EXPENSE
    assert service.income_commands[0].amount == Decimal("881.12")


def test_manual_income_create_returns_field_errors_without_calling_service() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operationType": "income",
                "accountId": str(primary_account_id(operation)),
                "amount": "0",
                "operationDate": "2026-07-20",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["fieldErrors"] == {
        "income.amount": ["Сумма должна быть больше нуля."]
    }
    assert service.income_commands == []


def test_manual_income_create_maps_workspace_reference_error() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app([operation])
    service.create_error = LedgerPostingError("Account is not available in this workspace.")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operationType": "income",
                "accountId": str(primary_account_id(operation)),
                "amount": "1250.00",
                "operationDate": "2026-07-20",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "account_unavailable",
        "message": "Выбранный счёт недоступен в этом workspace.",
        "fieldErrors": {"accountId": ["Выбранный счёт недоступен в этом workspace."]},
    }


def test_manual_create_maps_idempotency_payload_conflict_to_409() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app([operation])
    service.create_error = OperationIdempotencyConflictError()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operationType": "income",
                "accountId": str(primary_account_id(operation)),
                "amount": "1250.00",
                "operationDate": "2026-07-20",
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_conflict"


def test_manual_income_create_requires_financial_write_permission() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app([operation], role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operationType": "income",
                "accountId": str(primary_account_id(operation)),
                "amount": "1250.00",
                "operationDate": "2026-07-20",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.income_commands == []


def test_manual_transfer_create_dispatches_server_owned_transfer_command() -> None:
    operation = manual_operation(OperationType.TRANSFER)
    app, service, _, workspace_id = manual_ledger_app([operation])
    idempotency_key = uuid4()
    assert operation.source_entry is not None
    assert operation.destination_entry is not None
    source_account_id = operation.source_entry.account_id
    destination_account_id = operation.destination_entry.account_id

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            headers={"Idempotency-Key": str(idempotency_key)},
            json={
                "operationType": "transfer",
                "sourceAccountId": str(source_account_id),
                "destinationAccountId": str(destination_account_id),
                "amount": "65000.00",
                "operationDate": "2026-07-20",
                "description": "Между своими счетами",
            },
        )

    assert response.status_code == 201
    assert response.json()["money"] == {
        "amount": "65000.00",
        "currency": "RUB",
        "operationType": "transfer",
        "entryDirection": "transfer",
    }
    assert service.workspace_ids == [workspace_id, workspace_id]
    assert service.transfer_commands == [
        CreateManualTransferCommand(
            source_account_id=source_account_id,
            destination_account_id=destination_account_id,
            amount=Decimal("65000.00"),
            operation_date=date(2026, 7, 20),
            description="Между своими счетами",
            idempotency_key=idempotency_key,
        )
    ]


def test_manual_create_requires_idempotency_key() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            json={
                "operationType": "income",
                "accountId": str(primary_account_id(operation)),
                "amount": "10.00",
                "operationDate": "2026-07-20",
            },
        )

    assert response.status_code == 422
    assert service.income_commands == []


def test_manual_expense_update_dispatches_versioned_workspace_command() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, workspace_id = manual_ledger_app([operation])
    account_id = primary_account_id(operation)

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/manual-ledger/{operation.id}",
            json={
                "version": 3,
                "operationType": "expense",
                "accountId": str(account_id),
                "amount": "70000,25",
                "operationDate": "2026-07-22",
                "description": "Исправленная аренда",
                "categoryId": None,
                "propertyId": None,
            },
        )

    assert response.status_code == 200
    assert service.workspace_ids == [workspace_id, workspace_id]
    assert service.update_commands == [
        UpdateManualOperationCommand(
            operation_id=operation.id,
            operation_type=OperationType.EXPENSE,
            account_id=account_id,
            amount=Decimal("70000.25"),
            operation_date=date(2026, 7, 22),
            description="Исправленная аренда",
            category_id=None,
            property_id=None,
            destination_account_id=None,
            expected_version=3,
        )
    ]


def test_manual_update_maps_stale_version_to_409() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app([operation])
    service.update_error = OperationVersionConflictError()

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/manual-ledger/{operation.id}",
            json={
                "version": 2,
                "operationType": "income",
                "accountId": str(primary_account_id(operation)),
                "amount": "10.00",
                "operationDate": "2026-07-20",
                "description": "Несохранённый draft",
            },
        )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "operation_version_conflict",
        "message": "Операция уже изменилась в другом окне.",
    }


def test_manual_cancel_dispatches_versioned_transition_and_returns_capabilities() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, workspace_id = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/manual-ledger/{operation.id}/cancel",
            json={"version": 3},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["version"] == 4
    assert response.json()["capabilities"] == {
        "canEdit": False,
        "canCancel": False,
        "canRestore": True,
        "canDelete": True,
        "readonlyReason": None,
    }
    assert service.workspace_ids == [workspace_id, workspace_id]
    assert service.lifecycle_calls == [("cancel", operation.id, 3)]


def test_manual_restore_dispatches_versioned_transition() -> None:
    operation = replace(
        manual_operation(OperationType.INCOME),
        status=OperationStatus.IGNORED,
        version=4,
    )
    app, service, _, _ = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/manual-ledger/{operation.id}/restore",
            json={"version": 4},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["version"] == 5
    assert service.lifecycle_calls == [("restore", operation.id, 4)]


def test_manual_lifecycle_maps_state_conflict_to_409() -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app([operation])
    service.lifecycle_error = ManualOperationLifecycleConflictError(
        "Only confirmed manual operations can be cancelled."
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/manual-ledger/{operation.id}/cancel",
            json={"version": 3},
        )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "operation_state_conflict",
        "message": "Состояние операции уже изменилось. Обновите список.",
    }


def test_manual_lifecycle_requires_write_permission() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, _ = manual_ledger_app(
        [operation],
        role=WorkspaceRole.VIEWER,
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/manual-ledger/{operation.id}/cancel",
            json={"version": 3},
        )

    assert response.status_code == 403
    assert service.lifecycle_calls == []


def test_manual_delete_dispatches_versioned_command_and_returns_no_content() -> None:
    operation = replace(
        manual_operation(OperationType.EXPENSE),
        status=OperationStatus.IGNORED,
        version=4,
    )
    app, service, _, workspace_id = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            f"/api/v1/manual-ledger/{operation.id}",
            json={"version": 4},
        )

    assert response.status_code == 204
    assert response.content == b""
    assert service.workspace_ids == [workspace_id]
    assert service.lifecycle_calls == [("delete", operation.id, 4)]
    assert service.operations == []


def test_manual_delete_maps_invalid_state_to_409() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, _ = manual_ledger_app([operation])
    service.lifecycle_error = ManualOperationLifecycleConflictError(
        "Cancel a manual operation before deleting it."
    )

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            f"/api/v1/manual-ledger/{operation.id}",
            json={"version": 3},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "operation_state_conflict"


def test_manual_delete_requires_write_permission() -> None:
    operation = replace(
        manual_operation(OperationType.EXPENSE),
        status=OperationStatus.IGNORED,
    )
    app, service, _, _ = manual_ledger_app(
        [operation],
        role=WorkspaceRole.VIEWER,
    )

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            f"/api/v1/manual-ledger/{operation.id}",
            json={"version": 3},
        )

    assert response.status_code == 403
    assert service.lifecycle_calls == []


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


def primary_account_id(operation: ManualOperationView) -> UUID:
    assert operation.primary_entry is not None
    return operation.primary_entry.account_id


def account_view(name: str) -> AccountView:
    return AccountView(
        id=uuid4(),
        name=name,
        type=AccountType.CHECKING,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("0.00"),
    )
