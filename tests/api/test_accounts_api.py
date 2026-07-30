from decimal import Decimal

from accounts_support import account_detail_app, accounts_app

from api_client import ApiTestClient as TestClient
from app.features.accounts.models import AccountType
from app.features.accounts.schemas import CreateAccountCommand
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


def test_account_directory_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/accounts")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_account_detail_returns_account_relative_transfer_and_source_target() -> None:
    app, ledger, references, workspace_id, account_id = account_detail_app()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/accounts/{account_id}?status=confirmed&type=transfer&page=2&per_page=25"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["account"] == {
        "id": str(account_id),
        "name": "Основной",
        "accountType": "card",
        "currency": "RUB",
        "initialBalance": "10000.00",
        "balance": "8500.00",
        "isActive": True,
    }
    assert payload["items"][0]["amount"] == "-1500.00"
    assert payload["items"][0]["transferRoute"] == "Основной → Накопительный"
    assert payload["items"][0]["sourceTarget"] == {
        "kind": "manual",
        "uploadedDocumentId": None,
        "rawTransactionId": None,
    }
    assert ledger.calls[0][0:2] == (workspace_id, account_id)
    assert ledger.calls[0][2].status == OperationStatus.CONFIRMED
    assert ledger.calls[0][2].operation_type == OperationType.TRANSFER
    assert ledger.calls[0][3].page == 2
    assert references.workspace_ids == [workspace_id]


def test_account_detail_returns_workspace_scoped_not_found() -> None:
    app, ledger, references, _, account_id = account_detail_app(found=False)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/accounts/{account_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "account_not_found"
    assert len(ledger.calls) == 1
    assert references.workspace_ids == []


def test_account_detail_rejects_inverted_date_range() -> None:
    app, ledger, _, _, account_id = account_detail_app()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/accounts/{account_id}?date_from=2026-07-30&date_to=2026-07-01"
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"
    assert ledger.calls == []


def test_account_directory_returns_decimal_strings_and_server_capabilities() -> None:
    app, service, workspace_id = accounts_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/accounts")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": str(service.directory.items[0].id),
                "name": "Основной",
                "accountType": "card",
                "currency": "RUB",
                "initialBalance": "10000.00",
                "balance": "9118.88",
                "balanceDirection": "positive",
                "movementCount": 4,
                "isActive": True,
                "updatedAt": "2026-07-30T12:00:00Z",
                "capabilities": {
                    "canArchive": True,
                    "canRestore": False,
                },
            }
        ],
        "accountTypes": ["cash", "card", "deposit", "checking", "other"],
        "capabilities": {
            "canCreate": True,
            "readonlyReasonCode": None,
        },
    }
    assert service.read_calls == [(workspace_id, True)]


def test_account_directory_is_readonly_for_viewer() -> None:
    app, service, workspace_id = accounts_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get("/api/v1/accounts")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "canCreate": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }
    assert service.read_calls == [(workspace_id, False)]


def test_account_create_dispatches_workspace_scoped_command() -> None:
    app, service, workspace_id = accounts_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/accounts",
            json={
                "name": "  Резервный   счёт ",
                "accountType": "deposit",
                "currency": " rub ",
                "initialBalance": "-1500,25",
            },
        )

    assert response.status_code == 201
    assert response.json()["id"] == str(service.directory.items[0].id)
    assert service.create_calls == [
        (
            workspace_id,
            CreateAccountCommand(
                name="Резервный счёт",
                account_type=AccountType.DEPOSIT,
                currency="RUB",
                initial_balance=Decimal("-1500.25"),
            ),
        )
    ]


def test_account_create_returns_field_errors_without_calling_service() -> None:
    app, service, _ = accounts_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/accounts",
            json={
                "name": " ",
                "accountType": "card",
                "currency": "RUBLE",
                "initialBalance": "not-money",
                "unexpectedField": "value",
            },
        )

    assert response.status_code == 422
    assert response.json()["error"]["fieldErrors"] == {
        "name": ["Название счета обязательно."],
        "currency": ["Валюта должна быть трехбуквенным кодом."],
        "initialBalance": ["Введите корректный начальный баланс."],
        "unexpectedField": ["Неизвестное поле."],
    }
    assert service.create_calls == []


def test_account_create_requires_financial_write_permission() -> None:
    app, service, _ = accounts_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/accounts",
            json={
                "name": "Резерв",
                "accountType": "deposit",
                "currency": "RUB",
                "initialBalance": "0.00",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.create_calls == []


def test_account_archive_uses_explicit_stale_state_guards() -> None:
    app, service, workspace_id = accounts_app()
    account = service.directory.items[0]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/accounts/{account.id}/archive",
            json={
                "expectedActive": True,
                "expectedUpdatedAt": "2026-07-30T12:00:00Z",
            },
        )

    assert response.status_code == 200
    assert response.json()["isActive"] is False
    assert response.json()["capabilities"] == {
        "canArchive": False,
        "canRestore": True,
    }
    assert service.lifecycle_calls == [
        (
            workspace_id,
            account.id,
            False,
            True,
            account.updated_at,
        )
    ]


def test_account_archive_rejects_invalid_expected_state() -> None:
    app, service, _ = accounts_app()
    account = service.directory.items[0]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/accounts/{account.id}/archive",
            json={
                "expectedActive": False,
                "expectedUpdatedAt": "2026-07-30T12:00:00Z",
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "account_state_conflict"
    assert service.lifecycle_calls == []
