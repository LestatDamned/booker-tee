from properties_support import properties_app

from api_client import ApiTestClient as TestClient
from app.features.properties.schemas import CreatePropertyCommand
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


def test_property_create_normalizes_and_dispatches_workspace_scoped_command() -> None:
    app, service, workspace_id = properties_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/properties",
            json={
                "name": "  Квартира   на Мира ",
                "shortName": "  Дом  ",
                "address": "  Красноярск,   ул. Мира, 1 ",
            },
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(service.directory.items[0].id)
    assert service.create_calls == [
        (
            workspace_id,
            CreatePropertyCommand(
                name="Квартира на Мира",
                short_name="Дом",
                address="Красноярск, ул. Мира, 1",
            ),
        )
    ]


def test_property_create_normalizes_empty_optional_fields_to_null() -> None:
    app, service, workspace_id = properties_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/properties",
            json={"name": "Проект", "shortName": "  ", "address": "\n"},
        )

    assert response.status_code == 201
    assert service.create_calls == [
        (
            workspace_id,
            CreatePropertyCommand(name="Проект", short_name=None, address=None),
        )
    ]


def test_property_create_applies_bounds_after_whitespace_normalization() -> None:
    app, service, workspace_id = properties_app()
    bounded_name = "Н" * 255
    bounded_short_name = "К" * 64

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/properties",
            json={
                "name": f"   {bounded_name}   ",
                "shortName": f"  {bounded_short_name}  ",
            },
        )

    assert response.status_code == 201
    assert service.create_calls == [
        (
            workspace_id,
            CreatePropertyCommand(
                name=bounded_name,
                short_name=bounded_short_name,
                address=None,
            ),
        )
    ]


def test_property_create_returns_field_errors_without_calling_service() -> None:
    app, service, _ = properties_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/properties",
            json={
                "name": " ",
                "shortName": "x" * 65,
                "unexpectedField": "value",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["fieldErrors"] == {
        "name": ["Название объекта обязательно."],
        "shortName": ["String should have at most 64 characters"],
        "unexpectedField": ["Неизвестное поле."],
    }
    assert service.create_calls == []


def test_property_create_requires_financial_write_permission() -> None:
    app, service, _ = properties_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/properties",
            json={"name": "Проект"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.create_calls == []
