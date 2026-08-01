from properties_support import properties_app

from api_client import ApiTestClient as TestClient
from app.features.properties.models import PropertyStatus
from app.features.properties.schemas import (
    CreatePropertyCommand,
    PropertyLifecycleCommand,
    UpdatePropertyCommand,
)
from app.features.properties.service import (
    PropertyLifecycleConflictError,
    PropertyNotFoundError,
    PropertyUpdateConflictError,
)
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


def test_property_update_dispatches_workspace_identity_and_expected_timestamp() -> None:
    app, service, workspace_id = properties_app()
    property_ = service.directory.items[0]

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/properties/{property_.id}",
            json={
                "name": "  Квартира   после ремонта ",
                "shortName": "  Дом ",
                "address": "  ул. Мира, 1 ",
                "expectedUpdatedAt": "2026-08-01T08:30:00Z",
            },
        )

    assert response.status_code == 200
    assert service.update_calls == [
        (
            workspace_id,
            property_.id,
            UpdatePropertyCommand(
                name="Квартира после ремонта",
                short_name="Дом",
                address="ул. Мира, 1",
                expected_updated_at=property_.updated_at,
            ),
        )
    ]


def test_property_update_maps_not_found_and_stale_snapshot() -> None:
    app, service, _ = properties_app()
    property_ = service.directory.items[0]
    payload = {
        "name": "Квартира",
        "shortName": "Дом",
        "address": "ул. Мира, 1",
        "expectedUpdatedAt": "2026-08-01T08:30:00Z",
    }

    with TestClient(app) as client:
        service.update_error = PropertyNotFoundError("missing")
        missing = client.put(f"/api/v1/properties/{property_.id}", json=payload)
        service.update_error = PropertyUpdateConflictError("stale")
        conflict = client.put(f"/api/v1/properties/{property_.id}", json=payload)

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "property_not_found"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "property_update_conflict"


def test_property_update_reuses_create_field_validation() -> None:
    app, service, _ = properties_app()
    property_ = service.directory.items[0]

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/properties/{property_.id}",
            json={
                "name": " ",
                "shortName": "x" * 65,
                "expectedUpdatedAt": property_.updated_at.isoformat(),
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["fieldErrors"] == {
        "name": ["Название объекта обязательно."],
        "shortName": ["String should have at most 64 characters"],
    }
    assert service.update_calls == []


def test_property_update_requires_write_permission_and_valid_token() -> None:
    app, service, _ = properties_app(role=WorkspaceRole.VIEWER)
    property_ = service.directory.items[0]

    with TestClient(app) as client:
        forbidden = client.put(
            f"/api/v1/properties/{property_.id}",
            json={
                "name": "Проект",
                "expectedUpdatedAt": "2026-08-01T08:30:00Z",
            },
        )

    assert forbidden.status_code == 403
    assert service.update_calls == []

    owner_app, owner_service, _ = properties_app()
    with TestClient(owner_app) as client:
        invalid = client.put(
            f"/api/v1/properties/{owner_service.directory.items[0].id}",
            json={"name": "Проект", "expectedUpdatedAt": "not-a-date"},
        )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["fieldErrors"] == {
        "expectedUpdatedAt": ["Input should be a valid datetime or date, invalid character in year"]
    }
    assert owner_service.update_calls == []


def test_property_archive_returns_committed_snapshot_and_explicit_impact() -> None:
    app, service, workspace_id = properties_app()
    property_ = service.directory.items[0]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/properties/{property_.id}/archive",
            json={
                "expectedStatus": "active",
                "expectedUpdatedAt": property_.updated_at.isoformat(),
            },
        )

    assert response.status_code == 200
    assert response.json()["property"]["status"] == "archived"
    assert response.json()["property"]["capabilities"] == {
        "canUpdate": True,
        "canArchive": False,
        "canRestore": True,
    }
    assert response.json()["impact"] == {
        "historyPreserved": True,
        "activeRulesUnchanged": True,
        "availableForNewReferences": False,
    }
    assert service.lifecycle_calls == [
        (
            workspace_id,
            property_.id,
            PropertyStatus.ARCHIVED,
            PropertyLifecycleCommand(
                expected_status=PropertyStatus.ACTIVE,
                expected_updated_at=property_.updated_at,
            ),
        )
    ]


def test_property_restore_dispatches_archived_snapshot() -> None:
    app, service, workspace_id = properties_app()
    property_ = service.directory.items[1]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/properties/{property_.id}/restore",
            json={
                "expectedStatus": "archived",
                "expectedUpdatedAt": property_.updated_at.isoformat(),
            },
        )

    assert response.status_code == 200
    assert response.json()["property"]["status"] == "active"
    assert response.json()["impact"]["availableForNewReferences"] is True
    assert service.lifecycle_calls == [
        (
            workspace_id,
            property_.id,
            PropertyStatus.ACTIVE,
            PropertyLifecycleCommand(
                expected_status=PropertyStatus.ARCHIVED,
                expected_updated_at=property_.updated_at,
            ),
        )
    ]


def test_property_lifecycle_maps_wrong_state_missing_stale_and_permission() -> None:
    app, service, _ = properties_app()
    property_ = service.directory.items[0]
    payload = {
        "expectedStatus": "active",
        "expectedUpdatedAt": property_.updated_at.isoformat(),
    }

    with TestClient(app) as client:
        wrong_state = client.post(f"/api/v1/properties/{property_.id}/restore", json=payload)
        service.lifecycle_error = PropertyNotFoundError("missing")
        missing = client.post(f"/api/v1/properties/{property_.id}/archive", json=payload)
        service.lifecycle_error = PropertyLifecycleConflictError("stale")
        conflict = client.post(f"/api/v1/properties/{property_.id}/archive", json=payload)

    assert wrong_state.status_code == 409
    assert wrong_state.json()["error"]["code"] == "property_lifecycle_conflict"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "property_not_found"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "property_lifecycle_conflict"

    viewer_app, viewer_service, _ = properties_app(role=WorkspaceRole.VIEWER)
    viewer_property = viewer_service.directory.items[0]
    with TestClient(viewer_app) as client:
        forbidden = client.post(
            f"/api/v1/properties/{viewer_property.id}/archive",
            json={
                "expectedStatus": "active",
                "expectedUpdatedAt": viewer_property.updated_at.isoformat(),
            },
        )

    assert forbidden.status_code == 403
    assert viewer_service.lifecycle_calls == []
