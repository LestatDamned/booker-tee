from uuid import uuid4

from transaction_rules_support import transaction_rules_app

from api_client import ApiTestClient as TestClient
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
