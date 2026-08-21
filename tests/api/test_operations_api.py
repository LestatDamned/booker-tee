from uuid import uuid4

import pytest
from fastapi import FastAPI
from operations_support import operation, operations_app

from api_client import ApiTestClient as TestClient
from app.api.dependencies import get_api_request_context
from app.api.errors import ApiError
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.listing import LedgerPagination
from app.features.ledger.schemas.operations import ImportOperationProvenanceDto
from app.features.workspaces.domain.types import WorkspaceRole


def test_operations_returns_all_sources_and_target_outside_page_contract(app: FastAPI) -> None:
    operations = [operation(source) for source in OperationSource]
    target = operations[1]
    app, reader, references, workspace_id = operations_app(app, operations)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/operations?type=expense&source=bank_pdf&status=confirmed"
            f"&search=++Аренда++за++август++&operation_id={target.id}"
            "&page=2&per_page=25"
        )

    assert response.status_code == 200
    payload = response.json()
    assert target.account is not None
    assert isinstance(target.provenance, ImportOperationProvenanceDto)
    assert {item["source"] for item in payload["items"]} == {
        "manual",
        "bank_pdf",
        "debt",
        "system",
    }
    imported = next(item for item in payload["items"] if item["source"] == "bank_pdf")
    assert imported == {
        "id": str(target.id),
        "version": 3,
        "operationType": "expense",
        "source": "bank_pdf",
        "status": "confirmed",
        "operationDate": "2026-08-11",
        "description": "Аренда за август",
        "money": {"amount": "65000.00", "currency": "RUB"},
        "account": {
            "id": str(target.account.id),
            "name": "Основной счёт",
            "currency": "RUB",
        },
        "sourceAccount": None,
        "destinationAccount": None,
        "category": None,
        "property": None,
        "provenance": {
            "kind": "import",
            "uploadedDocumentId": str(target.provenance.uploaded_document_id),
            "rawTransactionId": str(target.provenance.raw_transaction_id),
        },
        "capabilities": {
            "canEdit": True,
            "editKind": "imported",
            "canCancel": False,
            "canRestore": False,
            "canDelete": False,
            "readonlyReason": None,
        },
    }
    assert payload["targetOperationId"] == str(target.id)
    assert payload["targetOperation"] == imported
    assert payload["filterOptions"]["sources"] == [
        "manual",
        "bank_pdf",
        "debt",
        "system",
    ]
    assert payload["capabilities"] == {"canCreate": True, "readonlyReason": None}
    assert reader.list_calls[0][0] == workspace_id
    assert reader.list_calls[0][1] is True
    assert reader.list_calls[0][2].source is OperationSource.BANK_PDF
    assert reader.list_calls[0][2].operation_type is OperationType.EXPENSE
    assert reader.list_calls[0][2].status is OperationStatus.CONFIRMED
    assert reader.list_calls[0][2].search == "Аренда за август"
    assert reader.list_calls[0][3] == LedgerPagination(page=2, per_page=25)
    assert reader.get_calls == [(workspace_id, target.id, True)]
    assert references.workspace_ids == [workspace_id]


def test_operations_masks_unknown_target_and_normalizes_invalid_filters(app: FastAPI) -> None:
    app, reader, _, workspace_id = operations_app(app, [])
    foreign_operation_id = uuid4()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/operations?operation_id={foreign_operation_id}&type=wrong&source=wrong"
            "&date_from=wrong&page=wrong&per_page=999"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["targetOperationId"] is None
    assert payload["targetOperation"] is None
    assert reader.list_calls[0][0] == workspace_id
    assert reader.list_calls[0][2].operation_type is None
    assert reader.list_calls[0][2].source is None
    assert reader.list_calls[0][2].status is OperationStatus.CONFIRMED
    assert reader.list_calls[0][2].date_from is None
    assert reader.list_calls[0][3] == LedgerPagination(page=1, per_page=200)
    assert reader.get_calls == [(workspace_id, foreign_operation_id, True)]


@pytest.mark.parametrize(
    ("query", "expected_status"),
    [
        pytest.param("", OperationStatus.CONFIRMED, id="confirmed-by-default"),
        pytest.param("?status=all", None, id="all-statuses"),
    ],
)
def test_operations_normalizes_status_filter(
    app: FastAPI,
    query: str,
    expected_status: OperationStatus | None,
) -> None:
    app, reader, _, _ = operations_app(app, [])

    with TestClient(app) as client:
        response = client.get(f"/api/v1/operations{query}")

    assert response.status_code == 200
    assert len(reader.list_calls) == 1
    assert reader.list_calls[0][2].status is expected_status


def test_operations_exposes_readonly_collection_capability_for_viewer(app: FastAPI) -> None:
    app, reader, _, _ = operations_app(
        app,
        [operation(OperationSource.MANUAL)],
        role=WorkspaceRole.VIEWER,
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/operations")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "canCreate": False,
        "readonlyReason": "Операции доступны только для просмотра согласно вашей роли.",
    }
    assert reader.list_calls[0][1] is False


def test_operations_rejects_reversed_date_range_before_reading(app: FastAPI) -> None:
    app, reader, references, _ = operations_app(app, [])

    with TestClient(app) as client:
        response = client.get("/api/v1/operations?date_from=2026-08-12&date_to=2026-08-01")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"
    assert reader.list_calls == []
    assert references.workspace_ids == []


def test_operations_requires_authentication(app: FastAPI) -> None:
    app, reader, references, _ = operations_app(app, [])

    async def unauthorized() -> None:
        raise ApiError(
            status_code=401,
            code="authentication_required",
            message="Требуется вход.",
        )

    app.dependency_overrides[get_api_request_context] = unauthorized

    with TestClient(app) as client:
        response = client.get("/api/v1/operations")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
    assert reader.list_calls == []
    assert references.workspace_ids == []
