from datetime import date

from categories_support import categories_app, category_detail_app

from api_client import ApiTestClient as TestClient
from app.features.categories.application.detail import CategoryDetailFilterError
from app.features.categories.models import CategoryKind
from app.features.categories.schemas import (
    CategoryLifecycleCommand,
    CreateCategoryCommand,
    UpdateCategoryCommand,
)
from app.features.categories.service import (
    CategoryArchiveBlockedError,
    CategoryDeleteBlockedError,
    CategoryDeleteDependencies,
    CategoryError,
    CategoryLifecycleConflictError,
    CategorySystemImmutableError,
    CategoryUpdateConflictError,
)
from app.features.ledger.domain.types import OperationType
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
        "deleteBlockers": {
            "operationCount": 12,
            "ruleCount": 3,
            "rawSuggestionCount": 0,
            "childCategoryCount": 0,
            "reasonCodes": ["active_category", "operations", "rules"],
        },
        "updatedAt": "2026-08-01T08:30:00Z",
        "capabilities": {
            "canUpdate": True,
            "canArchive": False,
            "canRestore": False,
            "canDelete": False,
            "archiveBlockedReasonCode": "active_rules",
        },
    }
    assert payload["items"][1]["capabilities"] == {
        "canUpdate": False,
        "canArchive": False,
        "canRestore": False,
        "canDelete": False,
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


def test_category_archive_and_restore_return_committed_policy_impact() -> None:
    app, service, _, workspace_id, category_id = category_detail_app()
    category = service.directory.items[0]

    with TestClient(app) as client:
        archived = client.post(
            f"/api/v1/categories/{category_id}/archive",
            json={
                "expectedStatus": True,
                "expectedUpdatedAt": category.updated_at.isoformat(),
            },
        )
        restored = client.post(
            f"/api/v1/categories/{category_id}/restore",
            json={
                "expectedStatus": False,
                "expectedUpdatedAt": category.updated_at.isoformat(),
            },
        )

    assert archived.status_code == 200
    assert archived.json()["category"]["isActive"] is False
    assert archived.json()["impact"] == {
        "historyPreserved": True,
        "rulesUnchanged": True,
        "availableForNewReferences": False,
    }
    assert restored.status_code == 200
    assert restored.json()["category"]["isActive"] is True
    assert service.lifecycle_calls == [
        (
            workspace_id,
            category_id,
            False,
            CategoryLifecycleCommand(
                expected_status=True,
                expected_updated_at=category.updated_at,
            ),
        ),
        (
            workspace_id,
            category_id,
            True,
            CategoryLifecycleCommand(
                expected_status=False,
                expected_updated_at=category.updated_at,
            ),
        ),
    ]


def test_category_lifecycle_maps_conflict_archive_blocker_and_permission() -> None:
    app, service, _, _, category_id = category_detail_app()
    category = service.directory.items[0]
    payload = {
        "expectedStatus": True,
        "expectedUpdatedAt": category.updated_at.isoformat(),
    }

    with TestClient(app) as client:
        wrong_state = client.post(f"/api/v1/categories/{category_id}/restore", json=payload)
        service.lifecycle_error = CategoryLifecycleConflictError("stale")
        conflict = client.post(f"/api/v1/categories/{category_id}/archive", json=payload)
        service.lifecycle_error = CategoryArchiveBlockedError(2)
        blocked = client.post(f"/api/v1/categories/{category_id}/archive", json=payload)

    assert wrong_state.status_code == 409
    assert conflict.json()["error"]["code"] == "category_lifecycle_conflict"
    assert blocked.status_code == 422
    assert blocked.json()["error"] == {
        "code": "category_archive_blocked",
        "message": "Сначала отключите активные правила категории.",
        "details": {"activeRuleCount": 2},
    }

    viewer_app, viewer_service, _, _, viewer_category_id = category_detail_app(
        role=WorkspaceRole.VIEWER
    )
    with TestClient(viewer_app) as client:
        forbidden = client.post(
            f"/api/v1/categories/{viewer_category_id}/archive",
            json=payload,
        )
    assert forbidden.status_code == 403
    assert viewer_service.lifecycle_calls == []


def test_category_delete_returns_identity_and_full_blocker_details() -> None:
    app, service, _, workspace_id, category_id = category_detail_app()
    category = service.directory.items[0]
    payload = {
        "expectedStatus": False,
        "expectedUpdatedAt": category.updated_at.isoformat(),
    }

    with TestClient(app) as client:
        deleted = client.request(
            "DELETE",
            f"/api/v1/categories/{category_id}",
            json=payload,
        )
        service.delete_error = CategoryDeleteBlockedError(
            CategoryDeleteDependencies(
                operation_count=2,
                rule_count=3,
                raw_suggestion_count=4,
                child_category_count=1,
            )
        )
        blocked = client.request(
            "DELETE",
            f"/api/v1/categories/{category_id}",
            json=payload,
        )

    assert deleted.status_code == 200
    assert deleted.json() == {"deletedId": str(category_id), "name": "Продукты"}
    assert service.delete_calls[0][0] == workspace_id
    assert blocked.status_code == 422
    assert blocked.json()["error"]["details"] == {
        "operationCount": 2,
        "ruleCount": 3,
        "rawSuggestionCount": 4,
        "childCategoryCount": 1,
    }


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


def test_category_detail_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/api/v1/categories/{service_category_id()}")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_category_detail_dispatches_filters_and_returns_money_strings() -> None:
    app, _, reader, workspace_id, category_id = category_detail_app()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/categories/{category_id}",
            params={
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
                "currency": "rub",
                "type": "expense",
                "operations_page": "2",
                "operations_page_size": "10",
                "search": "  супермаркет  ",
            },
        )

    assert response.status_code == 200
    assert response.json()["summary"] == {
        "currency": "RUB",
        "income": "100.00",
        "expense": "35.00",
        "profit": "65.00",
    }
    assert response.json()["availableCurrencies"] == ["RUB", "USD"]
    assert reader.calls == [
        {
            "workspace_id": workspace_id,
            "category_id": category_id,
            "default_currency": "RUB",
            "can_write": True,
            "date_from": date(2026, 7, 1),
            "date_to": date(2026, 7, 31),
            "currency": "RUB",
            "operation_type": OperationType.EXPENSE,
            "search": "супермаркет",
            "operations_page": 2,
            "operations_page_size": 10,
        }
    ]


def test_category_detail_rejects_invalid_parameters_before_reader() -> None:
    app, _, reader, _, category_id = category_detail_app()

    with TestClient(app) as client:
        invalid_type = client.get(
            f"/api/v1/categories/{category_id}",
            params={"type": "transfer"},
        )
        invalid_page_size = client.get(
            f"/api/v1/categories/{category_id}",
            params={"operations_page_size": "101"},
        )
        invalid_search = client.get(
            f"/api/v1/categories/{category_id}",
            params={"search": "x" * 201},
        )

    assert invalid_type.status_code == 400
    assert invalid_type.json()["error"]["code"] == "invalid_category_filter"
    assert invalid_page_size.status_code == 400
    assert invalid_search.status_code == 400
    assert reader.calls == []


def test_category_detail_returns_same_not_found_contract() -> None:
    app, _, reader, _, category_id = category_detail_app()
    reader.not_found = True

    with TestClient(app) as client:
        response = client.get(f"/api/v1/categories/{category_id}")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "category_not_found",
        "message": "Категория не найдена.",
    }


def test_category_update_dispatches_optimistic_command_and_returns_fresh_detail() -> None:
    app, service, reader, workspace_id, category_id = category_detail_app()
    expected_updated_at = service.directory.items[0].updated_at

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/categories/{category_id}",
            params={"currency": "RUB", "search": "market"},
            json={
                "name": "  Еда и покупки  ",
                "kind": "mixed",
                "notes": "  Покупки   и возвраты ",
                "expectedUpdatedAt": expected_updated_at.isoformat(),
            },
        )

    assert response.status_code == 200
    assert service.update_calls == [
        (
            workspace_id,
            category_id,
            UpdateCategoryCommand(
                name="Еда и покупки",
                kind=CategoryKind.MIXED,
                notes="Покупки и возвраты",
                expected_updated_at=expected_updated_at,
            ),
        )
    ]
    assert reader.calls[0]["search"] == "market"
    assert response.json()["kindChangeImpact"] == {
        "existingOperationsUnchanged": True,
        "pickerCompatibilityMayChange": True,
        "operationCount": 12,
        "ruleCount": 3,
        "requiresConfirmation": True,
    }


def test_category_update_returns_stable_conflict_and_immutable_errors() -> None:
    app, service, reader, _, category_id = category_detail_app()
    request = {
        "name": "Еда",
        "kind": "expense",
        "expectedUpdatedAt": "2026-08-01T08:30:00Z",
    }
    service.update_error = CategoryUpdateConflictError("stale")

    with TestClient(app) as client:
        conflict = client.put(f"/api/v1/categories/{category_id}", json=request)
        service.update_error = CategorySystemImmutableError("system")
        immutable = client.put(f"/api/v1/categories/{category_id}", json=request)

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "category_update_conflict"
    assert immutable.status_code == 422
    assert immutable.json()["error"]["code"] == "category_system_immutable"
    assert len(reader.calls) == 2


def test_category_update_is_forbidden_for_viewer() -> None:
    app, service, reader, _, category_id = category_detail_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/categories/{category_id}",
            json={
                "name": "Еда",
                "kind": "expense",
                "expectedUpdatedAt": "2026-08-01T08:30:00Z",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.update_calls == []
    assert reader.calls == []


def test_category_update_validates_detail_context_before_mutation() -> None:
    app, service, reader, _, category_id = category_detail_app()
    reader.filter_error = CategoryDetailFilterError(
        "invalid_category_currency",
        "Эта валюта недоступна в текущем workspace.",
    )

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/categories/{category_id}",
            params={"currency": "EUR"},
            json={
                "name": "Еда",
                "kind": "expense",
                "expectedUpdatedAt": "2026-08-01T08:30:00Z",
            },
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_category_currency"
    assert service.update_calls == []


def service_category_id() -> str:
    return "00000000-0000-0000-0000-000000000001"
