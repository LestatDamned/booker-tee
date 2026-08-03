from uuid import uuid4

from workspaces_support import workspaces_app

from api_client import ApiTestClient as TestClient
from app.features.workspaces.commands import CreateWorkspaceCommand
from app.features.workspaces.domain.types import WorkspaceType
from app.features.workspaces.errors import (
    WorkspaceIdempotencyConflictError,
    WorkspaceNotFoundError,
    WorkspaceSwitchConflictError,
)
from app.main import create_app


def test_workspace_directory_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/workspaces")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_workspace_directory_returns_camel_case_server_capabilities() -> None:
    app, reader, _, _ = workspaces_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/workspaces")

    assert response.status_code == 200
    payload = response.json()
    assert payload["currentWorkspaceId"] == str(reader.directory.current_workspace_id)
    assert payload["capabilities"] == {"canCreate": True}
    assert payload["items"][0]["isCurrent"] is True
    assert payload["items"][0]["blockingReasonCodes"] == ["workspace_current"]
    assert payload["items"][1]["capabilities"]["canSelect"] is True
    assert payload["workspaceTypeOptions"][0] == {
        "value": "personal",
        "label": "Личное",
    }
    assert len(reader.calls) == 1
    assert reader.calls[0][0] != reader.directory.current_workspace_id
    assert reader.calls[0][1] == reader.directory.current_workspace_id


def test_workspace_create_normalizes_and_dispatches_idempotent_command() -> None:
    app, _, creator, _ = workspaces_app()
    idempotency_key = uuid4()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces",
            headers={"Idempotency-Key": str(idempotency_key)},
            json={
                "name": "  Семейный   бюджет ",
                "workspaceType": "family",
                "defaultCurrency": " rub ",
            },
        )

    assert response.status_code == 201
    assert creator.calls[0][1:] == (
        "workspace-session-token",
        CreateWorkspaceCommand(
            name="Семейный бюджет",
            workspace_type=WorkspaceType.FAMILY,
            default_currency="RUB",
        ),
        idempotency_key,
    )
    payload = response.json()
    assert payload["workspace"]["isCurrent"] is True
    assert payload["session"]["workspace"]["id"] == payload["workspace"]["id"]
    assert payload["navigationOutcome"] == {
        "kind": "workspace_changed",
        "href": "/app/workspaces",
        "boundary": "hard_reload",
    }


def test_workspace_create_requires_key_and_returns_workspace_field_errors() -> None:
    app, _, creator, _ = workspaces_app()

    with TestClient(app) as client:
        missing_key = client.post(
            "/api/v1/workspaces",
            json={"name": "Дом", "workspaceType": "personal"},
        )
        invalid = client.post(
            "/api/v1/workspaces",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": " ", "workspaceType": "personal"},
        )

    assert missing_key.status_code == 422
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "workspace_validation_error"
    assert invalid.json()["error"]["fieldErrors"] == {
        "name": ["Название пространства обязательно."]
    }
    assert creator.calls == []


def test_workspace_create_maps_idempotency_conflict() -> None:
    app, _, creator, _ = workspaces_app()
    creator.error = WorkspaceIdempotencyConflictError("Ключ уже использован.")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/workspaces",
            headers={"Idempotency-Key": str(uuid4())},
            json={"name": "Дом", "workspaceType": "personal"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_conflict"


def test_workspace_select_dispatches_expected_current_and_returns_session() -> None:
    app, reader, _, switcher = workspaces_app()
    target_id = reader.directory.items[1].id

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/workspaces/{target_id}/select",
            json={"expectedCurrentWorkspaceId": str(reader.directory.current_workspace_id)},
        )

    assert response.status_code == 200
    assert switcher.calls[0][1:] == (
        "workspace-session-token",
        target_id,
        reader.directory.current_workspace_id,
    )
    assert response.json()["session"]["workspace"]["id"] == str(target_id)
    assert response.json()["navigationOutcome"]["boundary"] == "hard_reload"


def test_workspace_select_masks_missing_and_reports_stale_current() -> None:
    app, reader, _, switcher = workspaces_app()
    target_id = reader.directory.items[1].id
    payload = {"expectedCurrentWorkspaceId": str(reader.directory.current_workspace_id)}

    with TestClient(app) as client:
        switcher.error = WorkspaceNotFoundError("foreign")
        missing = client.post(f"/api/v1/workspaces/{target_id}/select", json=payload)
        new_current_id = uuid4()
        switcher.error = WorkspaceSwitchConflictError(current_workspace_id=new_current_id)
        conflict = client.post(f"/api/v1/workspaces/{target_id}/select", json=payload)

    assert missing.status_code == 404
    assert missing.json()["error"] == {
        "code": "workspace_not_found",
        "message": "Пространство больше недоступно.",
    }
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "workspace_switch_conflict"
    assert conflict.json()["error"]["details"] == {"currentWorkspaceId": str(new_current_id)}
