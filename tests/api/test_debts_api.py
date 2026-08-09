from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from debts_support import NOW, debts_app

from api_client import ApiTestClient as TestClient
from app.features.debts.errors import (
    DebtAccountUnavailableError,
    DebtIdempotencyConflictError,
    DebtNotFoundError,
    DebtPaymentConflictError,
)
from app.features.debts.schemas import (
    AddExistingDebtCommand,
    GiveLoanCommand,
    OpenCreditCardCommand,
    TakeLoanCommand,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


def test_debts_require_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/debts")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_debt_list_serializes_money_and_viewer_capabilities() -> None:
    app, reader, _, context = debts_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get("/api/v1/debts")

    assert response.status_code == 200
    assert response.json()["items"][0]["balance"] == "-75.00"
    assert response.json()["items"][0]["outstanding"] == "75.00"
    assert response.json()["totals"] == [
        {
            "currency": "RUB",
            "receivable": "0.00",
            "payable": "75.00",
            "netPosition": "-75.00",
        }
    ]
    assert response.json()["capabilities"] == {
        "canCreate": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }
    assert reader.list_calls == [(context.workspace.workspace.id, False)]


def test_debt_detail_forwards_bounded_pagination_and_versions() -> None:
    app, reader, _, context = debts_app()
    debt_id = reader.detail.debt.account_id

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/debts/{debt_id}",
            params={"paymentsPage": 2, "paymentsPageSize": 10},
        )

    assert response.status_code == 200
    assert response.json()["paymentTotals"] == {
        "principal": "25.00",
        "interest": "10.00",
    }
    assert response.json()["payments"]["items"][0]["principal"]["version"] == 1
    assert response.json()["payments"]["items"][0]["canUndo"] is True
    assert reader.detail_calls == [(context.workspace.workspace.id, debt_id, True, 2, 10)]


def test_foreign_debt_uses_the_same_not_found_contract() -> None:
    app, _, _, _ = debts_app()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/debts/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "debt_not_found"


@pytest.mark.parametrize(
    ("payload", "command_type"),
    [
        (
            {
                "action": "add_existing",
                "name": "Ипотека",
                "kind": "mortgage",
                "currency": "RUB",
                "openingBalance": "100.00",
                "originalPrincipal": "120.00",
            },
            AddExistingDebtCommand,
        ),
        (
            {
                "action": "give_loan",
                "name": "Займ Ивану",
                "currency": "RUB",
                "amount": "100.00",
                "fundingAccountId": str(uuid4()),
                "operationDate": "2026-08-09",
            },
            GiveLoanCommand,
        ),
        (
            {
                "action": "take_loan",
                "name": "Кредит",
                "kind": "loan_payable",
                "currency": "RUB",
                "amount": "100.00",
                "receivingAccountId": str(uuid4()),
                "operationDate": "2026-08-09",
            },
            TakeLoanCommand,
        ),
        (
            {
                "action": "open_credit_card",
                "name": "Кредитка",
                "currency": "RUB",
                "creditLimit": "1000.00",
                "openingDebt": "0.00",
            },
            OpenCreditCardCommand,
        ),
    ],
)
def test_create_dispatches_all_supported_commands(
    payload: dict[str, str],
    command_type: type,
) -> None:
    app, reader, service, context = debts_app()
    idempotency_key = uuid4()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/debts",
            headers={"Idempotency-Key": str(idempotency_key)},
            json=payload,
        )

    assert response.status_code == 201
    assert response.json()["debt"]["accountId"] == str(reader.detail.debt.account_id)
    assert len(service.create_calls) == 1
    workspace, command = service.create_calls[0]
    assert workspace.workspace.id == context.workspace.workspace.id
    assert isinstance(command, command_type)
    assert command.idempotency_key == idempotency_key


def test_payment_dispatches_decimal_command_and_requires_write_permission() -> None:
    app, reader, service, context = debts_app()
    debt_id = reader.detail.debt.account_id
    settlement_id = uuid4()
    category_id = uuid4()
    idempotency_key = uuid4()
    payload = {
        "settlementAccountId": str(settlement_id),
        "principalAmount": "25,50",
        "interestAmount": "10.25",
        "operationDate": "2026-08-09",
        "interestCategoryId": str(category_id),
        "description": "Платёж",
    }

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/debts/{debt_id}/payments",
            headers={"Idempotency-Key": str(idempotency_key)},
            json=payload,
        )

    assert response.status_code == 201
    workspace, command = service.payment_calls[0]
    assert workspace.workspace.id == context.workspace.workspace.id
    assert command.debt_account_id == debt_id
    assert command.settlement_account_id == settlement_id
    assert command.principal_amount == Decimal("25.50")
    assert command.interest_amount == Decimal("10.25")
    assert command.operation_date == date(2026, 8, 9)
    assert command.idempotency_key == idempotency_key

    viewer_app, _, viewer_service, _ = debts_app(role=WorkspaceRole.VIEWER)
    with TestClient(viewer_app) as client:
        forbidden = client.post(
            f"/api/v1/debts/{debt_id}/payments",
            headers={"Idempotency-Key": str(uuid4())},
            json=payload,
        )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "financial_write_forbidden"
    assert viewer_service.payment_calls == []


def test_payment_rejects_zero_amounts_and_missing_idempotency_key() -> None:
    app, reader, service, _ = debts_app()
    debt_id = reader.detail.debt.account_id
    payload = {
        "settlementAccountId": str(uuid4()),
        "principalAmount": "0",
        "interestAmount": "0",
        "operationDate": "2026-08-09",
    }

    with TestClient(app) as client:
        zero = client.post(
            f"/api/v1/debts/{debt_id}/payments",
            headers={"Idempotency-Key": str(uuid4())},
            json=payload,
        )
        missing_key = client.post(
            f"/api/v1/debts/{debt_id}/payments",
            json={**payload, "principalAmount": "1.00"},
        )

    assert zero.status_code == 422
    assert missing_key.status_code == 422
    assert service.payment_calls == []


def test_lifecycle_and_undo_dispatch_expected_snapshots() -> None:
    app, reader, service, context = debts_app()
    debt_id = reader.detail.debt.account_id
    payment = reader.detail.payments.items[0]
    assert payment.principal is not None
    assert payment.interest is not None

    with TestClient(app) as client:
        archived = client.post(
            f"/api/v1/debts/{debt_id}/archive",
            json={
                "expectedActive": True,
                "expectedUpdatedAt": NOW.isoformat(),
            },
        )
        undone = client.post(
            f"/api/v1/debt-payments/{payment.payment_id}/undo",
            json={
                "expectedPrincipalOperationVersion": payment.principal.version,
                "expectedInterestOperationVersion": payment.interest.version,
            },
        )

    assert archived.status_code == 200
    action, workspace, lifecycle = service.lifecycle_calls[0]
    assert action == "archive"
    assert workspace.workspace.id == context.workspace.workspace.id
    assert lifecycle.debt_account_id == debt_id
    assert lifecycle.expected_active is True
    assert lifecycle.expected_updated_at == NOW
    assert undone.status_code == 200
    _, undo = service.undo_calls[0]
    assert undo.payment_id == payment.payment_id
    assert undo.expected_principal_operation_version == 1
    assert undo.expected_interest_operation_version == 1


def test_update_and_delete_dispatch_safe_maintenance_commands() -> None:
    app, reader, service, context = debts_app()
    debt_id = reader.detail.debt.account_id

    with TestClient(app) as client:
        updated = client.put(
            f"/api/v1/debts/{debt_id}",
            json={
                "name": " Кредит на ремонт ",
                "openedOn": "2026-01-01",
                "maturityDate": "2028-01-01",
                "creditLimit": None,
                "notes": "Условия уточнены",
                "expectedUpdatedAt": NOW.isoformat(),
            },
        )
        deleted = client.request(
            "DELETE",
            f"/api/v1/debts/{debt_id}",
            json={"expectedUpdatedAt": NOW.isoformat()},
        )

    assert updated.status_code == 200
    workspace, update = service.update_calls[0]
    assert workspace.workspace.id == context.workspace.workspace.id
    assert update.name == " Кредит на ремонт "
    assert update.expected_updated_at == NOW
    assert deleted.status_code == 200
    assert deleted.json() == {"deletedId": str(debt_id), "name": "Кредит"}
    _, delete = service.delete_calls[0]
    assert delete.debt_account_id == debt_id
    assert delete.expected_updated_at == NOW


def test_update_and_delete_require_financial_write_permission() -> None:
    app, reader, service, _ = debts_app(role=WorkspaceRole.VIEWER)
    debt_id = reader.detail.debt.account_id
    update_payload = {
        "name": "Кредит",
        "openedOn": None,
        "maturityDate": None,
        "creditLimit": None,
        "notes": None,
        "expectedUpdatedAt": NOW.isoformat(),
    }

    with TestClient(app) as client:
        updated = client.put(f"/api/v1/debts/{debt_id}", json=update_payload)
        deleted = client.request(
            "DELETE",
            f"/api/v1/debts/{debt_id}",
            json={"expectedUpdatedAt": NOW.isoformat()},
        )

    assert updated.status_code == 403
    assert deleted.status_code == 403
    assert service.update_calls == []
    assert service.delete_calls == []


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (DebtIdempotencyConflictError("conflict"), 409, "idempotency_conflict"),
        (DebtPaymentConflictError("stale"), 409, "debt_payment_conflict"),
        (DebtAccountUnavailableError("foreign"), 422, "debt_account_unavailable"),
        (DebtNotFoundError("foreign debt"), 404, "debt_not_found"),
    ],
)
def test_mutations_return_stable_error_contracts(
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    app, reader, service, _ = debts_app()
    service.error = error

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/debts/{reader.detail.debt.account_id}/payments",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "settlementAccountId": str(uuid4()),
                "principalAmount": "1.00",
                "operationDate": "2026-08-09",
            },
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code


def test_openapi_contains_debt_contracts() -> None:
    paths = create_app().openapi()["paths"]

    assert "/api/v1/debts" in paths
    assert "/api/v1/debts/{debt_id}" in paths
    assert {"get", "put", "delete"} <= set(paths["/api/v1/debts/{debt_id}"])
    assert "/api/v1/debts/{debt_id}/payments" in paths
    assert "/api/v1/debts/{debt_id}/archive" in paths
    assert "/api/v1/debts/{debt_id}/restore" in paths
    assert "/api/v1/debt-payments/{payment_id}/undo" in paths
