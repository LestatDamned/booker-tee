from categories_support import categories_app

from api_client import ApiTestClient as TestClient
from app.features.categories.models import CategoryKind
from app.features.categories.schemas import CreateCategoryCommand
from app.features.categories.service import CategoryError
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


def test_category_create_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/categories",
            json={"name": "Продукты", "kind": "expense"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_category_create_normalizes_and_dispatches_workspace_command() -> None:
    app, service, workspace_id, _ = categories_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/categories",
            json={
                "name": "  Домашние   животные ",
                "kind": "expense",
                "notes": "  Корм,   ветеринар и уход ",
            },
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(service.directory.items[0].id)
    assert service.create_calls == [
        (
            workspace_id,
            CreateCategoryCommand(
                name="Домашние животные",
                kind=CategoryKind.EXPENSE,
                notes="Корм, ветеринар и уход",
            ),
        )
    ]


def test_category_create_normalizes_empty_notes_to_null() -> None:
    app, service, workspace_id, _ = categories_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/categories",
            json={"name": "Питомцы", "kind": "mixed", "notes": " \n "},
        )

    assert response.status_code == 201
    assert service.create_calls == [
        (
            workspace_id,
            CreateCategoryCommand(
                name="Питомцы",
                kind=CategoryKind.MIXED,
                notes=None,
            ),
        )
    ]


def test_category_create_returns_stable_field_errors() -> None:
    app, service, _, _ = categories_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/categories",
            json={"name": " ", "kind": "expense", "notes": "x" * 1001},
        )

    assert response.status_code == 422
    assert response.json()["error"]["fieldErrors"] == {
        "name": ["Название категории обязательно."],
        "notes": ["String should have at most 1000 characters"],
    }
    assert service.create_calls == []


def test_category_create_rejects_oversized_name_and_unknown_kind() -> None:
    app, service, _, _ = categories_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/categories",
            json={"name": "Н" * 256, "kind": "asset"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["fieldErrors"] == {
        "name": ["String should have at most 255 characters"],
        "kind": ["Input should be 'income', 'expense', 'transfer', 'adjustment' or 'mixed'"],
    }
    assert service.create_calls == []


def test_category_create_maps_duplicate_name_to_name_field() -> None:
    app, service, _, _ = categories_app()
    service.create_error = CategoryError("Категория с таким названием уже есть.")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/categories",
            json={"name": "Продукты", "kind": "expense"},
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "category_validation_error",
        "message": "Категория с таким названием уже есть.",
        "fieldErrors": {"name": ["Категория с таким названием уже есть."]},
    }


def test_category_create_is_forbidden_for_viewer() -> None:
    app, service, _, _ = categories_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/categories",
            json={"name": "Питомцы", "kind": "expense"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.create_calls == []
