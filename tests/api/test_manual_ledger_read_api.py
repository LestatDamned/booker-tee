from dataclasses import replace

from manual_ledger_support import (
    filter_references,
    manual_ledger_app,
    manual_operation,
    primary_account_id,
)

from api_client import ApiTestClient as TestClient
from app.features.ledger.application.listing import LedgerPagination
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.workspaces.domain.types import WorkspaceRole


def test_manual_ledger_returns_decimal_money_and_explicit_semantics() -> None:
    operation = manual_operation(OperationType.EXPENSE)
    app, service, reference_reader, workspace_id = manual_ledger_app([operation])
    reference_reader.references = filter_references()

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
        "operationType": "expense",
        "operationDate": "2026-07-20",
        "description": "Аренда за июль",
        "status": "confirmed",
        "money": {"amount": "65000.00", "currency": "RUB"},
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
    assert response.json()["items"][0]["operationType"] == "transfer"


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
        "readonlyReason": "Ручные операции доступны только для просмотра согласно вашей роли.",
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
    reference_reader.references = filter_references()

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


def test_manual_operation_edit_rejects_non_editable_state() -> None:
    operation = replace(
        manual_operation(OperationType.INCOME),
        status=OperationStatus.IGNORED,
    )
    app, service, reference_reader, _ = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.get(f"/api/v1/manual-ledger/{operation.id}/edit")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "operation_not_editable"
    assert len(service.workspace_ids) == 1
    assert reference_reader.workspace_ids == []
