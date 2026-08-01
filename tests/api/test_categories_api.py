from categories_support import categories_app

from api_client import ApiTestClient as TestClient
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


def test_category_directory_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/categories")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_category_directory_returns_workspace_snapshot_and_capabilities() -> None:
    app, service, workspace_id, workspace_type = categories_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/categories")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0] == {
        "id": str(service.directory.items[0].id),
        "name": "Продукты",
        "kind": "expense",
        "isActive": True,
        "isSystem": False,
        "systemKey": None,
        "notes": "Супермаркеты и доставка",
        "operationCount": 12,
        "ruleCount": 3,
        "activeRuleCount": 1,
        "updatedAt": "2026-08-01T08:30:00Z",
        "capabilities": {
            "canUpdate": True,
            "canArchive": False,
            "canRestore": False,
            "archiveBlockedReasonCode": "active_rules",
        },
    }
    assert payload["items"][1]["capabilities"] == {
        "canUpdate": False,
        "canArchive": False,
        "canRestore": False,
        "archiveBlockedReasonCode": None,
    }
    assert payload["kindOptions"] == [
        {"value": "expense", "label": "Расход", "description": "Для списаний."}
    ]
    assert payload["capabilities"] == {
        "canCreate": True,
        "readonlyReasonCode": None,
    }
    assert service.read_calls == [(workspace_id, workspace_type, True)]


def test_category_directory_is_readonly_for_viewer() -> None:
    app, service, workspace_id, workspace_type = categories_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get("/api/v1/categories")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "canCreate": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }
    assert response.json()["items"][0]["capabilities"]["canUpdate"] is False
    assert service.read_calls == [(workspace_id, workspace_type, False)]
