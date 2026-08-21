from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from accounts_support import account_correction_app, account_detail_app, accounts_app
from fastapi import FastAPI

from api_client import ApiTestClient as TestClient
from app.api.v1.accounts.detail_mapping import AccountDetailResponseMapper
from app.features.accounts.models import AccountType
from app.features.accounts.schemas import CreateAccountCommand, UpdateAccountCommand
from app.features.ledger.application.account_ledger import (
    AccountView,
    OperationRefMoneyEntryView,
    OperationRefView,
)
from app.features.ledger.application.imported_operations import (
    UpdateImportedOperationReviewFieldsCommand,
)
from app.features.ledger.domain.types import (
    OperationSource,
    OperationStatus,
    OperationType,
)
from app.features.ledger.errors import OperationVersionConflictError
from app.features.workspaces.domain.types import WorkspaceRole


def test_account_directory_requires_authentication(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/accounts")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_account_detail_returns_account_relative_transfer_and_source_target(
    app: FastAPI,
) -> None:
    app, ledger, references, workspace_id, account_id = account_detail_app(app)

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
        "updatedAt": "2026-07-30T12:00:00Z",
        "capabilities": {
            "canUpdate": True,
            "canArchive": True,
            "canRestore": False,
        },
    }
    assert payload["items"][0]["amount"] == "-1500.00"
    assert payload["items"][0]["transferRoute"] == "Основной → Накопительный"
    assert payload["items"][0]["sourceTarget"] == {
        "kind": "manual",
        "uploadedDocumentId": None,
        "rawTransactionId": None,
        "debtAccountId": None,
    }
    assert payload["items"][0]["capabilities"] == {
        "canEditReviewFields": False,
        "readonlyReasonCode": "imported_operation_only",
    }
    assert ledger.calls[0][0:2] == (workspace_id, account_id)
    assert ledger.calls[0][2].status == OperationStatus.CONFIRMED
    assert ledger.calls[0][2].operation_type == OperationType.TRANSFER
    assert ledger.calls[0][3].page == 2
    assert references.workspace_ids == [workspace_id]


def test_account_detail_returns_workspace_scoped_not_found(app: FastAPI) -> None:
    app, ledger, references, _, account_id = account_detail_app(app, found=False)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/accounts/{account_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "account_not_found"
    assert len(ledger.calls) == 1
    assert references.workspace_ids == []


def test_account_detail_links_debt_operation_to_debt_workflow() -> None:
    debt_account_id = uuid4()
    debt_account = AccountView(
        id=debt_account_id,
        name="Ипотека",
        type=AccountType.DEBT,
        currency="RUB",
        is_active=True,
        initial_balance=Decimal("-100000.00"),
        updated_at=datetime(2026, 8, 9, tzinfo=UTC),
    )
    operation = OperationRefView(
        id=uuid4(),
        version=1,
        type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        source=OperationSource.DEBT,
        operation_date=date(2026, 8, 9),
        description="Платёж",
        category=None,
        property=None,
        money_entries=[
            OperationRefMoneyEntryView(
                account_id=debt_account_id,
                account=debt_account,
                amount=Decimal("1000.00"),
            )
        ],
        raw_transactions=[],
    )

    target = AccountDetailResponseMapper._source_target(operation)

    assert target.kind == "debt"
    assert target.debt_account_id == debt_account_id


def test_account_detail_hides_mutations_from_viewer(app: FastAPI) -> None:
    app, _, _, _, account_id = account_detail_app(app, role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/accounts/{account_id}")

    assert response.status_code == 200
    assert response.json()["account"]["capabilities"] == {
        "canUpdate": False,
        "canArchive": False,
        "canRestore": False,
    }
    assert response.json()["items"][0]["capabilities"] == {
        "canEditReviewFields": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }


def test_account_detail_rejects_inverted_date_range(app: FastAPI) -> None:
    app, ledger, _, _, account_id = account_detail_app(app)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/accounts/{account_id}?date_from=2026-07-30&date_to=2026-07-01"
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"
    assert ledger.calls == []


def test_imported_operation_correction_returns_committed_movement(app: FastAPI) -> None:
    (
        app,
        ledger,
        use_case,
        workspace_id,
        account_id,
        operation_id,
        category_id,
    ) = account_correction_app(app)
    property_id = uuid4()

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/accounts/{account_id}/operations/{operation_id}/review-fields",
            json={
                "expectedVersion": 3,
                "description": "Такси",
                "categoryId": str(category_id),
                "propertyId": str(property_id),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 4
    assert payload["description"] == "Такси"
    assert payload["category"] == {
        "id": str(category_id),
        "name": "Транспорт",
    }
    assert payload["property"]["name"] == "Квартира"
    assert payload["amount"] == "-881.12"
    assert payload["capabilities"] == {
        "canEditReviewFields": True,
        "readonlyReasonCode": None,
    }
    assert ledger.imported_calls == [
        (workspace_id, operation_id, account_id),
        (workspace_id, operation_id, account_id),
    ]
    assert use_case.calls[0][0].workspace.id == workspace_id
    assert use_case.calls[0][1] == UpdateImportedOperationReviewFieldsCommand(
        operation_id=operation_id,
        expected_version=3,
        category_id=category_id,
        property_id=property_id,
        description="Такси",
    )


def test_imported_operation_correction_requires_account_association(app: FastAPI) -> None:
    app, _, use_case, _, account_id, operation_id, _ = account_correction_app(
        app,
        found=False,
    )

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/accounts/{account_id}/operations/{operation_id}/review-fields",
            json={
                "expectedVersion": 3,
                "description": "Такси",
                "categoryId": None,
                "propertyId": None,
            },
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "account_operation_not_found"
    assert use_case.calls == []


def test_imported_operation_correction_maps_stale_version_to_conflict(app: FastAPI) -> None:
    app, _, use_case, _, account_id, operation_id, _ = account_correction_app(
        app, error=OperationVersionConflictError()
    )

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/accounts/{account_id}/operations/{operation_id}/review-fields",
            json={
                "expectedVersion": 2,
                "description": "Такси",
                "categoryId": None,
                "propertyId": None,
            },
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "operation_version_conflict"
    assert len(use_case.calls) == 1


def test_imported_operation_correction_requires_financial_write_permission(
    app: FastAPI,
) -> None:
    app, ledger, use_case, _, account_id, operation_id, _ = account_correction_app(
        app, role=WorkspaceRole.VIEWER
    )

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/accounts/{account_id}/operations/{operation_id}/review-fields",
            json={
                "expectedVersion": 3,
                "description": "Такси",
                "categoryId": None,
                "propertyId": None,
            },
        )

    assert response.status_code == 403
    assert ledger.imported_calls == []
    assert use_case.calls == []


def test_account_directory_returns_decimal_strings_and_server_capabilities(
    app: FastAPI,
) -> None:
    app, service, workspace_id = accounts_app(app)

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


def test_account_directory_is_readonly_for_viewer(app: FastAPI) -> None:
    app, service, workspace_id = accounts_app(app, role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get("/api/v1/accounts")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "canCreate": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }
    assert service.read_calls == [(workspace_id, False)]


def test_account_create_dispatches_workspace_scoped_command(app: FastAPI) -> None:
    app, service, workspace_id = accounts_app(app)

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


def test_account_create_returns_field_errors_without_calling_service(app: FastAPI) -> None:
    app, service, _ = accounts_app(app)

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


def test_account_create_requires_financial_write_permission(app: FastAPI) -> None:
    app, service, _ = accounts_app(app, role=WorkspaceRole.VIEWER)

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


def test_account_update_uses_workspace_and_stale_write_token(app: FastAPI) -> None:
    app, service, workspace_id = accounts_app(app)
    account = service.directory.items[0]

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/accounts/{account.id}",
            json={
                "name": "Расчётный",
                "accountType": "checking",
                "currency": "RUB",
                "initialBalance": "12000.50",
                "expectedUpdatedAt": "2026-07-30T12:00:00Z",
            },
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Расчётный"
    assert service.update_calls == [
        (
            workspace_id,
            account.id,
            UpdateAccountCommand(
                name="Расчётный",
                account_type=AccountType.CHECKING,
                currency="RUB",
                initial_balance=Decimal("12000.50"),
                expected_updated_at=account.updated_at,
            ),
        )
    ]


def test_account_update_requires_financial_write_permission(app: FastAPI) -> None:
    app, service, _ = accounts_app(app, role=WorkspaceRole.VIEWER)
    account = service.directory.items[0]

    with TestClient(app) as client:
        response = client.put(
            f"/api/v1/accounts/{account.id}",
            json={
                "name": account.name,
                "accountType": account.account_type,
                "currency": account.currency,
                "initialBalance": str(account.initial_balance),
                "expectedUpdatedAt": "2026-07-30T12:00:00Z",
            },
        )

    assert response.status_code == 403
    assert service.update_calls == []


@pytest.mark.parametrize(
    ("action", "expected_active", "target_active"),
    [
        pytest.param("archive", True, False, id="archive"),
        pytest.param("restore", False, True, id="restore"),
    ],
)
def test_account_lifecycle_uses_explicit_stale_state_guards(
    app: FastAPI,
    action: str,
    expected_active: bool,
    target_active: bool,
) -> None:
    app, service, workspace_id = accounts_app(app)
    account = service.directory.items[0]

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/accounts/{account.id}/{action}",
            json={
                "expectedActive": expected_active,
                "expectedUpdatedAt": "2026-07-30T12:00:00Z",
            },
        )

    assert response.status_code == 200
    assert response.json()["isActive"] is target_active
    assert response.json()["capabilities"] == {
        "canArchive": target_active,
        "canRestore": not target_active,
    }
    assert service.lifecycle_calls == [
        (
            workspace_id,
            account.id,
            target_active,
            expected_active,
            account.updated_at,
        )
    ]


def test_account_archive_rejects_invalid_expected_state(app: FastAPI) -> None:
    app, service, _ = accounts_app(app)
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
