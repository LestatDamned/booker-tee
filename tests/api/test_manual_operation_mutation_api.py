from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from manual_ledger_support import manual_ledger_app, manual_operation, primary_account_id

from api_client import ApiTestClient as TestClient
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.ledger.errors import (
    ManualOperationLifecycleConflictError,
    OperationVersionConflictError,
)
from app.features.ledger.schemas.manual import UpdateManualIncomeExpenseCommand
from app.features.workspaces.domain.types import WorkspaceRole


def test_manual_expense_update_dispatches_versioned_workspace_command(app: FastAPI) -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, workspace_id = manual_ledger_app(app, [operation])
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
    assert service.workspace_ids == [workspace_id]
    assert service.update_commands == [
        UpdateManualIncomeExpenseCommand(
            operation_id=operation.id,
            operation_type=OperationType.EXPENSE,
            account_id=account_id,
            amount=Decimal("70000.25"),
            operation_date=date(2026, 7, 22),
            description="Исправленная аренда",
            category_id=None,
            property_id=None,
            expected_version=3,
        )
    ]


def test_manual_update_maps_stale_version_to_409(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app(app, [operation])
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


def test_manual_cancel_dispatches_versioned_transition_and_returns_capabilities(
    app: FastAPI,
) -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, workspace_id = manual_ledger_app(app, [operation])

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
    assert service.workspace_ids == [workspace_id]
    assert service.lifecycle_calls == [("cancel", operation.id, 3)]


def test_manual_restore_dispatches_versioned_transition(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME).model_copy(
        update={
            "status": OperationStatus.IGNORED,
            "version": 4,
        },
    )
    app, service, _, _ = manual_ledger_app(app, [operation])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/manual-ledger/{operation.id}/restore",
            json={"version": 4},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["version"] == 5
    assert service.lifecycle_calls == [("restore", operation.id, 4)]


def test_manual_lifecycle_maps_state_conflict_to_409(app: FastAPI) -> None:
    operation = manual_operation(OperationType.INCOME)
    app, service, _, _ = manual_ledger_app(app, [operation])
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


def test_manual_lifecycle_requires_write_permission(app: FastAPI) -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, _ = manual_ledger_app(
        app,
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


def test_manual_delete_dispatches_versioned_command_and_returns_no_content(
    app: FastAPI,
) -> None:
    operation = manual_operation(OperationType.EXPENSE).model_copy(
        update={
            "status": OperationStatus.IGNORED,
            "version": 4,
        },
    )
    app, service, _, workspace_id = manual_ledger_app(app, [operation])

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


def test_manual_delete_maps_invalid_state_to_409(app: FastAPI) -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, _, _ = manual_ledger_app(app, [operation])
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


def test_manual_delete_requires_write_permission(app: FastAPI) -> None:
    operation = manual_operation(OperationType.EXPENSE).model_copy(
        update={"status": OperationStatus.IGNORED},
    )
    app, service, _, _ = manual_ledger_app(
        app,
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
