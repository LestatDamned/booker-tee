from manual_ledger_support import filter_references, manual_ledger_app, manual_operation

from api_client import ApiTestClient as TestClient
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.workspaces.domain.types import WorkspaceRole


def test_manual_ledger_has_no_parallel_list_endpoint() -> None:
    app, _, _, _ = manual_ledger_app([])

    with TestClient(app) as client:
        response = client.get("/api/v1/manual-ledger")

    assert response.status_code == 405


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
    operation = manual_operation(OperationType.INCOME).model_copy(
        update={"status": OperationStatus.IGNORED},
    )
    app, service, reference_reader, _ = manual_ledger_app([operation])

    with TestClient(app) as client:
        response = client.get(f"/api/v1/manual-ledger/{operation.id}/edit")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "operation_not_editable"
    assert len(service.workspace_ids) == 1
    assert reference_reader.workspace_ids == []
