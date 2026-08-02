from uuid import uuid4

from transaction_rules_support import transaction_rules_app, transaction_rules_mutation_app

from api_client import ApiTestClient as TestClient
from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
    UpdateTransactionRuleCommand,
)
from app.features.transaction_rules.errors import (
    TransactionRuleNotFoundError,
    TransactionRuleUpdateConflictError,
    TransactionRuleValidationError,
)
from app.features.transaction_rules.schemas import TransactionRuleDirectoryStatus
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


def test_transaction_rule_directory_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/transaction-rules")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_transaction_rule_directory_dispatches_normalized_workspace_filters() -> None:
    app, reader, workspace_id = transaction_rules_app()
    category_id = uuid4()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/transaction-rules",
            params={
                "q": "  ozon   travel ",
                "category_id": str(category_id),
                "status": "disabled",
                "page": "2",
                "page_size": "25",
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
        }
    ]


def test_transaction_rule_directory_is_readonly_for_viewer() -> None:
    app, reader, _ = transaction_rules_app(role=WorkspaceRole.VIEWER)

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


def test_transaction_rule_directory_rejects_invalid_filters_without_calling_reader() -> None:
    app, reader, _ = transaction_rules_app()

    with TestClient(app) as client:
        invalid_status = client.get(
            "/api/v1/transaction-rules",
            params={"status": "archived"},
        )
        invalid_page_size = client.get(
            "/api/v1/transaction-rules",
            params={"page_size": "101"},
        )
        invalid_category = client.get(
            "/api/v1/transaction-rules",
            params={"category_id": "foreign"},
        )

    assert invalid_status.status_code == 400
    assert invalid_page_size.status_code == 400
    assert invalid_category.status_code == 400
    assert invalid_status.json()["error"]["code"] == "invalid_transaction_rule_filter"
    assert reader.calls == []


def test_create_transaction_rule_maps_command_and_returns_committed_summary() -> None:
    app, mutations = transaction_rules_mutation_app()
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


def test_create_and_seed_require_writer_and_valid_payload() -> None:
    viewer_app, viewer = transaction_rules_mutation_app(role=WorkspaceRole.VIEWER)
    owner_app, owner = transaction_rules_mutation_app()

    with TestClient(viewer_app) as client:
        forbidden = client.post(
            "/api/v1/transaction-rules/seed-defaults",
        )
    with TestClient(owner_app) as client:
        invalid = client.post(
            "/api/v1/transaction-rules",
            headers={"Idempotency-Key": str(uuid4())},
            json={"pattern": "", "matchType": "contains"},
        )
        seeded = client.post("/api/v1/transaction-rules/seed-defaults")

    assert forbidden.status_code == 403
    assert viewer.calls == []
    assert invalid.status_code == 422
    assert len(owner.calls) == 1
    assert owner.calls[0][0] == "seed"
    assert seeded.json() == {
        "createdRules": 3,
        "existingRules": 50,
        "createdCategories": 1,
    }


def test_edit_load_and_update_dispatch_workspace_scoped_version() -> None:
    app, mutations = transaction_rules_mutation_app()
    rule = mutations.item
    assert rule.outcome.category is not None
    assert rule.outcome.property is not None

    with TestClient(app) as client:
        loaded = client.get(f"/api/v1/transaction-rules/{rule.id}/edit")
        updated = client.put(
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

    assert loaded.status_code == 200
    assert loaded.json()["item"]["id"] == str(rule.id)
    assert loaded.json()["references"]["properties"][0]["isActive"] is False
    assert updated.status_code == 200
    action, call = mutations.calls[-1]
    assert action == "update"
    command = call["command"]
    assert isinstance(command, UpdateTransactionRuleCommand)
    assert command.rule_id == rule.id
    assert command.expected_updated_at == rule.updated_at


def test_edit_requires_writer_and_maps_not_found_conflict_and_field_error() -> None:
    viewer_app, viewer = transaction_rules_mutation_app(role=WorkspaceRole.VIEWER)
    app, mutations = transaction_rules_mutation_app()
    rule_id = mutations.item.id

    with TestClient(viewer_app) as client:
        forbidden = client.get(f"/api/v1/transaction-rules/{viewer.item.id}/edit")
    assert forbidden.status_code == 403
    assert viewer.calls == []

    cases = [
        (TransactionRuleNotFoundError(), 404, "transaction_rule_not_found"),
        (TransactionRuleUpdateConflictError(), 409, "transaction_rule_update_conflict"),
        (
            TransactionRuleValidationError("Недоступная категория.", field="category_id"),
            422,
            "transaction_rule_validation_error",
        ),
    ]
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
        for error, expected_status, expected_code in cases:
            mutations.error = error
            response = client.put(f"/api/v1/transaction-rules/{rule_id}", json=payload)
            assert response.status_code == expected_status
            assert response.json()["error"]["code"] == expected_code
    assert response.json()["error"]["fieldErrors"] == {"category_id": ["Недоступная категория."]}
