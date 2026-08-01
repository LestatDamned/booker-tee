from properties_support import properties_app

from api_client import ApiTestClient as TestClient
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


def test_property_directory_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/properties")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_property_directory_returns_workspace_snapshot_and_capabilities() -> None:
    app, service, workspace_id = properties_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/properties")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": str(service.directory.items[0].id),
                "name": "Квартира",
                "shortName": "Дом",
                "address": "Красноярск, ул. Мира, 1",
                "status": "active",
                "archivedAt": None,
                "updatedAt": "2026-08-01T08:30:00Z",
                "capabilities": {
                    "canUpdate": True,
                    "canArchive": True,
                    "canRestore": False,
                },
            },
            {
                "id": str(service.directory.items[1].id),
                "name": "Старый проект",
                "shortName": None,
                "address": None,
                "status": "archived",
                "archivedAt": "2026-08-01T08:30:00Z",
                "updatedAt": "2026-08-01T08:30:00Z",
                "capabilities": {
                    "canUpdate": True,
                    "canArchive": False,
                    "canRestore": True,
                },
            },
        ],
        "capabilities": {
            "canCreate": True,
            "readonlyReasonCode": None,
        },
    }
    assert service.read_calls == [(workspace_id, True)]


def test_property_directory_is_readonly_for_viewer() -> None:
    app, service, workspace_id = properties_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get("/api/v1/properties")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "canCreate": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }
    assert response.json()["items"][0]["capabilities"] == {
        "canUpdate": False,
        "canArchive": False,
        "canRestore": False,
    }
    assert service.read_calls == [(workspace_id, False)]
