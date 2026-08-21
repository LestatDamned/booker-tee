import pytest
from fastapi import FastAPI
from properties_support import properties_app

from api_client import ApiTestClient as TestClient
from app.features.properties.models import PropertyStatus
from app.features.properties.schemas import (
    CreatePropertyCommand,
    PropertyLifecycleCommand,
    UpdatePropertyCommand,
)
from app.features.properties.service import (
    PropertyError,
    PropertyLifecycleConflictError,
    PropertyNotFoundError,
    PropertyUpdateConflictError,
)
from app.features.workspaces.domain.types import WorkspaceRole


def test_property_directory_requires_authentication(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/properties")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_property_directory_returns_workspace_snapshot_and_capabilities(app: FastAPI) -> None:
    app, service, workspace_id = properties_app(app)

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


def test_property_directory_is_readonly_for_viewer(app: FastAPI) -> None:
    app, service, workspace_id = properties_app(app, role=WorkspaceRole.VIEWER)

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


def test_property_create_normalizes_and_dispatches_workspace_scoped_command(
    app: FastAPI,
) -> None:
    app, service, workspace_id = properties_app(app)

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


def test_property_create_normalizes_empty_optional_fields_to_null(app: FastAPI) -> None:
    app, service, workspace_id = properties_app(app)

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


def test_property_create_applies_bounds_after_whitespace_normalization(app: FastAPI) -> None:
    app, service, workspace_id = properties_app(app)
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


def test_property_create_returns_field_errors_without_calling_service(app: FastAPI) -> None:
    app, service, _ = properties_app(app)

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


def test_property_create_requires_financial_write_permission(app: FastAPI) -> None:
    app, service, _ = properties_app(app, role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/properties",
            json={"name": "Проект"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.create_calls == []


def test_property_update_dispatches_workspace_identity_and_expected_timestamp(
    app: FastAPI,
) -> None:
    app, service, workspace_id = properties_app(app)
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


@pytest.mark.parametrize(
    ("service_error", "status_code", "error_code"),
    [
        pytest.param(
            PropertyNotFoundError("missing"),
            404,
            "property_not_found",
            id="not-found",
        ),
        pytest.param(
            PropertyUpdateConflictError("stale"),
            409,
            "property_update_conflict",
            id="stale-snapshot",
        ),
    ],
)
def test_property_update_maps_service_error(
    app: FastAPI,
    service_error: PropertyError,
    status_code: int,
    error_code: str,
) -> None:
    app, service, _ = properties_app(app)
    property_ = service.directory.items[0]
    payload = {
        "name": "Квартира",
        "shortName": "Дом",
        "address": "ул. Мира, 1",
        "expectedUpdatedAt": "2026-08-01T08:30:00Z",
    }
    service.update_error = service_error

    with TestClient(app) as client:
        response = client.put(f"/api/v1/properties/{property_.id}", json=payload)

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert len(service.update_calls) == 1


def test_property_update_reuses_create_field_validation(app: FastAPI) -> None:
    app, service, _ = properties_app(app)
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


def test_property_update_requires_write_permission(app: FastAPI) -> None:
    app, service, _ = properties_app(app, role=WorkspaceRole.VIEWER)
    property_ = service.directory.items[0]

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/properties/{property_.id}",
            json={
                "name": "Проект",
                "expectedUpdatedAt": "2026-08-01T08:30:00Z",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.update_calls == []


def test_property_update_rejects_invalid_optimistic_timestamp(app: FastAPI) -> None:
    app, service, _ = properties_app(app)

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/properties/{service.directory.items[0].id}",
            json={"name": "Проект", "expectedUpdatedAt": "not-a-date"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["fieldErrors"] == {
        "expectedUpdatedAt": ["Input should be a valid datetime or date, invalid character in year"]
    }
    assert service.update_calls == []


@pytest.mark.parametrize(
    ("item_index", "action", "expected_status", "target_status"),
    [
        pytest.param(
            0,
            "archive",
            PropertyStatus.ACTIVE,
            PropertyStatus.ARCHIVED,
            id="archive",
        ),
        pytest.param(
            1,
            "restore",
            PropertyStatus.ARCHIVED,
            PropertyStatus.ACTIVE,
            id="restore",
        ),
    ],
)
def test_property_lifecycle_returns_committed_snapshot_and_explicit_impact(
    app: FastAPI,
    item_index: int,
    action: str,
    expected_status: PropertyStatus,
    target_status: PropertyStatus,
) -> None:
    app, service, workspace_id = properties_app(app)
    property_ = service.directory.items[item_index]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/properties/{property_.id}/{action}",
            json={
                "expectedStatus": expected_status,
                "expectedUpdatedAt": property_.updated_at.isoformat(),
            },
        )

    assert response.status_code == 200
    assert response.json()["property"]["status"] == target_status
    assert response.json()["property"]["capabilities"] == {
        "canUpdate": True,
        "canArchive": target_status == PropertyStatus.ACTIVE,
        "canRestore": target_status == PropertyStatus.ARCHIVED,
    }
    assert response.json()["impact"] == {
        "historyPreserved": True,
        "activeRulesUnchanged": True,
        "availableForNewReferences": target_status == PropertyStatus.ACTIVE,
    }
    assert service.lifecycle_calls == [
        (
            workspace_id,
            property_.id,
            target_status,
            PropertyLifecycleCommand(
                expected_status=expected_status,
                expected_updated_at=property_.updated_at,
            ),
        )
    ]


@pytest.mark.parametrize(
    ("action", "wrong_expected_status"),
    [
        pytest.param("archive", "archived", id="archive"),
        pytest.param("restore", "active", id="restore"),
    ],
)
def test_property_lifecycle_rejects_wrong_expected_state_before_dispatch(
    app: FastAPI,
    action: str,
    wrong_expected_status: str,
) -> None:
    app, service, _ = properties_app(app)
    property_ = service.directory.items[0]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/properties/{property_.id}/{action}",
            json={
                "expectedStatus": wrong_expected_status,
                "expectedUpdatedAt": property_.updated_at.isoformat(),
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "property_lifecycle_conflict"
    assert service.lifecycle_calls == []


@pytest.mark.parametrize(
    ("service_error", "status_code", "error_code"),
    [
        pytest.param(
            PropertyNotFoundError("missing"),
            404,
            "property_not_found",
            id="not-found",
        ),
        pytest.param(
            PropertyLifecycleConflictError("stale"),
            409,
            "property_lifecycle_conflict",
            id="stale-snapshot",
        ),
    ],
)
def test_property_lifecycle_maps_service_error(
    app: FastAPI,
    service_error: PropertyError,
    status_code: int,
    error_code: str,
) -> None:
    app, service, _ = properties_app(app)
    property_ = service.directory.items[0]
    service.lifecycle_error = service_error

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/properties/{property_.id}/archive",
            json={
                "expectedStatus": "active",
                "expectedUpdatedAt": property_.updated_at.isoformat(),
            },
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert len(service.lifecycle_calls) == 1


@pytest.mark.parametrize(
    ("action", "property_index", "expected_status"),
    [
        pytest.param("archive", 0, "active", id="archive"),
        pytest.param("restore", 1, "archived", id="restore"),
    ],
)
def test_property_lifecycle_is_forbidden_for_viewer(
    app: FastAPI,
    action: str,
    property_index: int,
    expected_status: str,
) -> None:
    app, service, _ = properties_app(app, role=WorkspaceRole.VIEWER)
    property_ = service.directory.items[property_index]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/properties/{property_.id}/{action}",
            json={
                "expectedStatus": expected_status,
                "expectedUpdatedAt": property_.updated_at.isoformat(),
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.lifecycle_calls == []
