from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI
from manual_ledger_support import manual_ledger_app, manual_operation, primary_account_id

from api_client import ApiTestClient as TestClient
from app.features.ledger.domain.types import OperationType
from app.features.ledger.errors import (
    AccountUnavailableError,
    OperationIdempotencyConflictError,
)
from app.features.ledger.schemas.manual import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)
from app.features.workspaces.domain.types import WorkspaceRole


def test_manual_income_create_dispatches_workspace_scoped_command(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, workspace_id = manual_ledger_app(app, [operation])
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
    assert response.json()["operationType"] == "income"
    assert service.workspace_ids == [workspace_id]
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


def test_manual_expense_create_preserves_expense_semantics(app: FastAPI) -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, workspace_id = manual_ledger_app(app, [operation])

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
    assert response.json()["money"] == {"amount": "65000.00", "currency": "RUB"}
    assert response.json()["operationType"] == "expense"
    assert service.workspace_ids == [workspace_id]
    assert service.income_commands[0].operation_type is OperationType.EXPENSE
    assert service.income_commands[0].amount == Decimal("881.12")


def test_manual_income_create_returns_field_errors_without_calling_service(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app(app, [operation])

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
    assert response.json()["error"]["fieldErrors"] == {"amount": ["Сумма должна быть больше нуля."]}
    assert service.income_commands == []


def test_manual_create_rejects_unknown_payload_fields(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app(app, [operation])

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/manual-ledger",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operationType": "income",
                "accountId": str(primary_account_id(operation)),
                "amount": "10.00",
                "operationDate": "2026-07-20",
                "unexpectedField": "ignored before this refactor",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["fieldErrors"] == {"unexpectedField": ["Неизвестное поле."]}
    assert service.income_commands == []


def test_manual_income_create_maps_workspace_reference_error(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app(app, [operation])
    service.create_error = AccountUnavailableError()

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


def test_manual_create_maps_idempotency_payload_conflict_to_409(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app(app, [operation])
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


def test_manual_income_create_requires_financial_write_permission(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app(app, [operation], role=WorkspaceRole.VIEWER)

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


def test_manual_transfer_create_dispatches_server_owned_transfer_command(app: FastAPI) -> None:
    operation = manual_operation(OperationType.TRANSFER)
    app, service, _, workspace_id = manual_ledger_app(app, [operation])
    idempotency_key = uuid4()
    assert operation.source_account is not None
    assert operation.destination_account is not None
    source_account_id = operation.source_account.id
    destination_account_id = operation.destination_account.id

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
    assert response.json()["money"] == {"amount": "65000.00", "currency": "RUB"}
    assert response.json()["operationType"] == "transfer"
    assert service.workspace_ids == [workspace_id]
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


def test_manual_create_requires_idempotency_key(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app(app, [operation])

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
