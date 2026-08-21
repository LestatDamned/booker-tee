from uuid import uuid4

import pytest
from fastapi import FastAPI
from transaction_rules_support import transaction_rules_app, transaction_rules_mutation_app

from api_client import ApiTestClient as TestClient
from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
    UpdateTransactionRuleCommand,
)
from app.features.transaction_rules.errors import (
    TransactionRuleActivationBlockedError,
    TransactionRuleDeleteBlockedError,
    TransactionRuleDeleteConflictError,
    TransactionRuleDeleteDependencies,
    TransactionRuleLifecycleConflictError,
    TransactionRuleNotFoundError,
    TransactionRuleUpdateConflictError,
    TransactionRuleValidationError,
)
from app.features.transaction_rules.schemas import TransactionRuleDirectoryStatus
from app.features.workspaces.domain.types import WorkspaceRole


def test_transaction_rule_directory_requires_authentication(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/transaction-rules")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_transaction_rule_directory_dispatches_normalized_workspace_filters(
    app: FastAPI,
) -> None:
    app, reader, workspace_id = transaction_rules_app(app)
    category_id = uuid4()
    rule_id = uuid4()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/transaction-rules",
            params={
                "q": "  ozon   travel ",
                "category_id": str(category_id),
                "status": "disabled",
                "page": "2",
                "page_size": "25",
                "rule_id": str(rule_id),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["condition"]["amountMin"] == "100.00"
    assert payload["items"][0]["outcome"]["category"]["name"] == "Маркетплейсы"
    assert payload["items"][0]["usage"] == {"directRawSuggestionCount": 4}
    assert payload["references"]["properties"][0]["isActive"] is False
    assert reader.calls == [
        {
            "workspace_id": workspace_id,
            "can_write": True,
            "search": "ozon travel",
            "category_id": category_id,
            "status": TransactionRuleDirectoryStatus.DISABLED,
            "page": 2,
            "page_size": 25,
            "target_rule_id": rule_id,
        }
    ]


def test_transaction_rule_directory_is_readonly_for_viewer(app: FastAPI) -> None:
    app, reader, _ = transaction_rules_app(app, role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get("/api/v1/transaction-rules")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "canCreate": False,
        "canSeedDefaults": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }
    assert response.json()["items"][0]["capabilities"] == {
        "canUpdate": False,
        "canEnable": False,
        "canDisable": False,
        "canDelete": False,
        "enableBlockedReasonCode": None,
        "deleteBlockedReasonCode": "active_rule",
    }
    assert reader.calls[0]["can_write"] is False


@pytest.mark.parametrize(
    ("query", "expected_field"),
    [
        pytest.param({"status": "archived"}, "status", id="status"),
        pytest.param({"page_size": "101"}, "page_size", id="page-size"),
        pytest.param({"category_id": "foreign"}, "category_id", id="category-id"),
    ],
)
def test_transaction_rule_directory_rejects_invalid_filter_without_calling_reader(
    app: FastAPI,
    query: dict[str, str],
    expected_field: str,
) -> None:
    app, reader, _ = transaction_rules_app(app)

    with TestClient(app) as client:
        response = client.get("/api/v1/transaction-rules", params=query)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_transaction_rule_filter"
    assert expected_field in response.json()["error"]["message"]
    assert reader.calls == []


def test_create_transaction_rule_maps_command_and_returns_committed_summary(
    app: FastAPI,
) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    idempotency_key = uuid4()
    category_id = uuid4()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/transaction-rules",
            headers={"Idempotency-Key": str(idempotency_key)},
            json={
                "name": "  Ozon purchases  ",
                "pattern": " OZON ",
                "matchType": "contains",
                "direction": "outflow",
                "amountMin": "100.00",
                "amountMax": "500.00",
                "operationType": "expense",
                "categoryId": str(category_id),
                "propertyId": None,
                "applicationMode": "suggest",
            },
        )

    assert response.status_code == 201
    assert response.json()["item"]["id"]
    assert response.json()["replayed"] is False
    action, call = mutations.calls[0]
    assert action == "create"
    assert call["idempotency_key"] == idempotency_key
    command = call["command"]
    assert isinstance(command, CreateTransactionRuleCommand)
    assert command.category_id == category_id
    assert str(command.amount_min) == "100.00"


@pytest.mark.parametrize(
    ("path", "headers", "payload"),
    [
        pytest.param(
            "/api/v1/transaction-rules",
            {"Idempotency-Key": str(uuid4())},
            {
                "pattern": "OZON",
                "matchType": "contains",
                "direction": "any",
                "applicationMode": "suggest",
            },
            id="create",
        ),
        pytest.param(
            "/api/v1/transaction-rules/seed-defaults",
            {},
            None,
            id="seed-defaults",
        ),
    ],
)
def test_transaction_rule_mutation_requires_writer(
    app: FastAPI,
    path: str,
    headers: dict[str, str],
    payload: dict[str, str] | None,
) -> None:
    app, mutations = transaction_rules_mutation_app(app, role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.post(path, headers=headers, json=payload)

    assert response.status_code == 403
    assert mutations.calls == []


def test_create_rejects_invalid_payload_before_mutation(app: FastAPI) -> None:
    app, mutations = transaction_rules_mutation_app(app)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/transaction-rules",
            headers={"Idempotency-Key": str(uuid4())},
            json={"pattern": "", "matchType": "contains"},
        )

    assert response.status_code == 422
    assert mutations.calls == []


def test_seed_returns_created_and_existing_counts(app: FastAPI) -> None:
    app, mutations = transaction_rules_mutation_app(app)

    with TestClient(app) as client:
        response = client.post("/api/v1/transaction-rules/seed-defaults")

    assert mutations.calls[0][0] == "seed"
    assert response.json() == {
        "createdRules": 3,
        "existingRules": 50,
        "createdCategories": 1,
    }


def test_edit_load_returns_item_and_archived_references(app: FastAPI) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    rule = mutations.item

    with TestClient(app) as client:
        response = client.get(f"/api/v1/transaction-rules/{rule.id}/edit")

    assert response.status_code == 200
    assert response.json()["item"]["id"] == str(rule.id)
    assert response.json()["references"]["properties"][0]["isActive"] is False
    action, call = mutations.calls[0]
    assert action == "edit"
    assert call["rule_id"] == rule.id


def test_update_dispatches_command_with_optimistic_version(app: FastAPI) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    rule = mutations.item
    assert rule.outcome.category is not None
    assert rule.outcome.property is not None

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/transaction-rules/{rule.id}",
            json={
                "name": "Ozon updated",
                "pattern": "OZON",
                "matchType": "exact",
                "direction": "outflow",
                "amountMin": "100.00",
                "amountMax": None,
                "operationType": "expense",
                "categoryId": str(rule.outcome.category.id),
                "propertyId": str(rule.outcome.property.id),
                "applicationMode": "suggest",
                "expectedUpdatedAt": rule.updated_at.isoformat(),
            },
        )

    assert response.status_code == 200
    action, call = mutations.calls[0]
    assert action == "update"
    command = call["command"]
    assert isinstance(command, UpdateTransactionRuleCommand)
    assert command.rule_id == rule.id
    assert command.expected_updated_at == rule.updated_at


def test_edit_requires_writer(app: FastAPI) -> None:
    viewer_app, viewer = transaction_rules_mutation_app(app, role=WorkspaceRole.VIEWER)

    with TestClient(viewer_app) as client:
        forbidden = client.get(f"/api/v1/transaction-rules/{viewer.item.id}/edit")

    assert forbidden.status_code == 403
    assert viewer.calls == []


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code", "expected_field_errors"),
    [
        pytest.param(
            TransactionRuleNotFoundError(),
            404,
            "transaction_rule_not_found",
            None,
            id="not-found",
        ),
        pytest.param(
            TransactionRuleUpdateConflictError(),
            409,
            "transaction_rule_update_conflict",
            None,
            id="stale-snapshot",
        ),
        pytest.param(
            TransactionRuleValidationError("Недоступная категория.", field="category_id"),
            422,
            "transaction_rule_validation_error",
            {"category_id": ["Недоступная категория."]},
            id="field-error",
        ),
    ],
)
def test_update_maps_application_errors(
    app: FastAPI,
    error: Exception,
    expected_status: int,
    expected_code: str,
    expected_field_errors: dict[str, list[str]] | None,
) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    rule_id = mutations.item.id
    mutations.error = error
    payload = {
        "name": None,
        "pattern": "OZON",
        "matchType": "contains",
        "direction": "any",
        "amountMin": None,
        "amountMax": None,
        "operationType": None,
        "categoryId": None,
        "propertyId": None,
        "applicationMode": "suggest",
        "expectedUpdatedAt": mutations.item.updated_at.isoformat(),
    }

    with TestClient(app) as client:
        response = client.put(f"/api/v1/transaction-rules/{rule_id}", json=payload)

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] == expected_code
    assert response.json()["error"].get("fieldErrors") == expected_field_errors


@pytest.mark.parametrize(
    ("action", "expected_active", "target_active"),
    [
        pytest.param("disable", True, False, id="disable"),
        pytest.param("enable", False, True, id="enable"),
    ],
)
def test_lifecycle_dispatches_expected_state_and_returns_truthful_impact(
    app: FastAPI,
    action: str,
    expected_active: bool,
    target_active: bool,
) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    rule = mutations.item
    payload = {
        "expectedActive": expected_active,
        "expectedUpdatedAt": rule.updated_at.isoformat(),
    }

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/transaction-rules/{rule.id}/{action}",
            json=payload,
        )

    assert response.status_code == 200
    assert response.json()["impact"] == {
        "futureMatchingChanged": True,
        "existingSuggestionsChanged": False,
        "existingSuggestionCount": 4,
    }
    assert mutations.calls[0][0] == "lifecycle"
    assert mutations.calls[0][1]["is_active"] is target_active
    assert mutations.calls[0][1]["expected_active"] is expected_active
    assert mutations.calls[0][1]["expected_updated_at"] == rule.updated_at


def test_lifecycle_requires_writer(app: FastAPI) -> None:
    viewer_app, viewer = transaction_rules_mutation_app(app, role=WorkspaceRole.VIEWER)
    payload = {
        "expectedActive": False,
        "expectedUpdatedAt": viewer.item.updated_at.isoformat(),
    }

    with TestClient(viewer_app) as client:
        forbidden = client.post(
            f"/api/v1/transaction-rules/{viewer.item.id}/disable",
            json=payload,
        )

    assert forbidden.status_code == 403
    assert viewer.calls == []


def test_lifecycle_maps_optimistic_conflict(app: FastAPI) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    payload = {
        "expectedActive": False,
        "expectedUpdatedAt": mutations.item.updated_at.isoformat(),
    }
    mutations.error = TransactionRuleLifecycleConflictError("Состояние правила уже изменилось.")

    with TestClient(app) as client:
        conflict = client.post(
            f"/api/v1/transaction-rules/{mutations.item.id}/enable", json=payload
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "transaction_rule_lifecycle_conflict"


@pytest.mark.parametrize(
    ("field", "expected_reason"),
    [
        pytest.param("categoryId", "category_inactive", id="category"),
        pytest.param("propertyId", "property_archived", id="property"),
        pytest.param("accountId", "account_unavailable", id="account"),
    ],
)
def test_lifecycle_maps_each_activation_blocker(
    app: FastAPI,
    field: str,
    expected_reason: str,
) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    payload = {
        "expectedActive": False,
        "expectedUpdatedAt": mutations.item.updated_at.isoformat(),
    }
    mutations.error = TransactionRuleActivationBlockedError(
        "Target is not available for an active rule.", field=field
    )

    with TestClient(app) as client:
        blocked = client.post(f"/api/v1/transaction-rules/{mutations.item.id}/enable", json=payload)

    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "transaction_rule_activation_blocked"
    assert blocked.json()["error"]["details"] == {"blockedReasonCode": expected_reason}


def test_delete_dispatches_stale_guards_and_returns_deleted_identity(app: FastAPI) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    rule = mutations.item

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            f"/api/v1/transaction-rules/{rule.id}",
            json={
                "expectedActive": False,
                "expectedUpdatedAt": rule.updated_at.isoformat(),
            },
        )

    assert response.status_code == 200
    assert response.json() == {"deletedId": str(rule.id), "name": rule.name}
    action, call = mutations.calls[0]
    assert action == "delete"
    assert call["rule_id"] == rule.id
    assert call["expected_active"] is False
    assert call["expected_updated_at"] == rule.updated_at


def test_delete_requires_writer(app: FastAPI) -> None:
    viewer_app, viewer = transaction_rules_mutation_app(app, role=WorkspaceRole.VIEWER)
    payload = {
        "expectedActive": False,
        "expectedUpdatedAt": viewer.item.updated_at.isoformat(),
    }

    with TestClient(viewer_app) as client:
        forbidden = client.request(
            "DELETE",
            f"/api/v1/transaction-rules/{viewer.item.id}",
            json=payload,
        )

    assert forbidden.status_code == 403
    assert viewer.calls == []


def test_delete_maps_optimistic_conflict(app: FastAPI) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    payload = {
        "expectedActive": False,
        "expectedUpdatedAt": mutations.item.updated_at.isoformat(),
    }
    mutations.error = TransactionRuleDeleteConflictError("Правило уже изменилось в другом окне.")

    with TestClient(app) as client:
        conflict = client.request(
            "DELETE",
            f"/api/v1/transaction-rules/{mutations.item.id}",
            json=payload,
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "transaction_rule_delete_conflict"


@pytest.mark.parametrize(
    ("dependencies", "expected_reason", "expected_count"),
    [
        pytest.param(
            TransactionRuleDeleteDependencies(is_active=True),
            "active_rule",
            0,
            id="active-rule",
        ),
        pytest.param(
            TransactionRuleDeleteDependencies(raw_suggestion_count=4),
            "raw_suggestions",
            4,
            id="import-history",
        ),
    ],
)
def test_delete_maps_each_dependency_blocker(
    app: FastAPI,
    dependencies: TransactionRuleDeleteDependencies,
    expected_reason: str,
    expected_count: int,
) -> None:
    app, mutations = transaction_rules_mutation_app(app)
    payload = {
        "expectedActive": False,
        "expectedUpdatedAt": mutations.item.updated_at.isoformat(),
    }
    mutations.error = TransactionRuleDeleteBlockedError(dependencies)

    with TestClient(app) as client:
        blocked = client.request(
            "DELETE",
            f"/api/v1/transaction-rules/{mutations.item.id}",
            json=payload,
        )

    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "transaction_rule_delete_blocked"
    assert blocked.json()["error"]["details"] == {
        "blockedReasonCode": expected_reason,
        "directRawSuggestionCount": expected_count,
    }
