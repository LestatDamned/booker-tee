from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from debts_support import NOW, debts_app
from fastapi import FastAPI

from api_client import ApiTestClient as TestClient
from app.features.debts.errors import (
    DebtAccountUnavailableError,
    DebtIdempotencyConflictError,
    DebtNotFoundError,
    DebtPaymentConflictError,
)
from app.features.debts.schemas import (
    AddExistingDebtCommand,
    DeleteDebtCommand,
    GiveLoanCommand,
    OpenCreditCardCommand,
    RecordDebtPaymentCommand,
    TakeLoanCommand,
    UpdateDebtCommand,
)
from app.features.workspaces.domain.types import WorkspaceRole


def test_debts_require_authentication(app: FastAPI) -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/debts")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_debt_list_serializes_money_and_viewer_capabilities(app: FastAPI) -> None:
    app, reader, _, context = debts_app(app, role=WorkspaceRole.VIEWER)

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


def test_debt_detail_forwards_bounded_pagination_and_versions(app: FastAPI) -> None:
    app, reader, _, context = debts_app(app)
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


def test_foreign_debt_uses_the_same_not_found_contract(app: FastAPI) -> None:
    app, _, _, _ = debts_app(app)

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
    app: FastAPI,
    payload: dict[str, str],
    command_type: type,
) -> None:
    app, reader, service, context = debts_app(app)
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


def test_payment_dispatches_decimal_command(app: FastAPI) -> None:
    app, reader, service, context = debts_app(app)
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
    assert service.payment_calls == [
        (
            context.workspace,
            RecordDebtPaymentCommand(
                debt_account_id=debt_id,
                settlement_account_id=settlement_id,
                principal_amount=Decimal("25.50"),
                interest_amount=Decimal("10.25"),
                operation_date=date(2026, 8, 9),
                interest_category_id=category_id,
                description="Платёж",
                notes=None,
                idempotency_key=idempotency_key,
            ),
        )
    ]
    assert len(reader.detail_calls) == 1


def test_payment_requires_financial_write_permission(app: FastAPI) -> None:
    app, reader, service, _ = debts_app(app, role=WorkspaceRole.VIEWER)
    debt_id = reader.detail.debt.account_id

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/debts/{debt_id}/payments",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "settlementAccountId": str(uuid4()),
                "principalAmount": "25.50",
                "interestAmount": "10.25",
                "operationDate": "2026-08-09",
                "interestCategoryId": str(uuid4()),
                "description": "Платёж",
            },
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.payment_calls == []
    assert reader.detail_calls == []


@pytest.mark.parametrize(
    ("principal_amount", "include_idempotency_key"),
    [
        pytest.param("0", True, id="zero-total"),
        pytest.param("1.00", False, id="missing-idempotency-key"),
    ],
)
def test_payment_rejects_invalid_request_before_dispatch(
    app: FastAPI,
    principal_amount: str,
    include_idempotency_key: bool,
) -> None:
    app, reader, service, _ = debts_app(app)
    debt_id = reader.detail.debt.account_id
    headers = {"Idempotency-Key": str(uuid4())} if include_idempotency_key else {}

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/debts/{debt_id}/payments",
            headers=headers,
            json={
                "settlementAccountId": str(uuid4()),
                "principalAmount": principal_amount,
                "interestAmount": "0",
                "operationDate": "2026-08-09",
            },
        )

    assert response.status_code == 422
    assert service.payment_calls == []
    assert reader.detail_calls == []


@pytest.mark.parametrize(
    ("action", "expected_active"),
    [
        pytest.param("archive", True, id="archive"),
        pytest.param("restore", False, id="restore"),
    ],
)
def test_lifecycle_dispatches_expected_snapshot(
    app: FastAPI,
    action: str,
    expected_active: bool,
) -> None:
    app, reader, service, context = debts_app(app)
    debt_id = reader.detail.debt.account_id

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/debts/{debt_id}/{action}",
            json={
                "expectedActive": expected_active,
                "expectedUpdatedAt": NOW.isoformat(),
            },
        )

    assert response.status_code == 200
    recorded_action, workspace, lifecycle = service.lifecycle_calls[0]
    assert recorded_action == action
    assert workspace.workspace.id == context.workspace.workspace.id
    assert lifecycle.debt_account_id == debt_id
    assert lifecycle.expected_active is expected_active
    assert lifecycle.expected_updated_at == NOW
    assert len(reader.detail_calls) == 1


def test_undo_dispatches_expected_operation_versions(app: FastAPI) -> None:
    app, reader, service, context = debts_app(app)
    payment = reader.detail.payments.items[0]
    assert payment.principal is not None
    assert payment.interest is not None

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/debt-payments/{payment.payment_id}/undo",
            json={
                "expectedPrincipalOperationVersion": payment.principal.version,
                "expectedInterestOperationVersion": payment.interest.version,
            },
        )

    assert response.status_code == 200
    workspace, undo = service.undo_calls[0]
    assert workspace.workspace.id == context.workspace.workspace.id
    assert undo.payment_id == payment.payment_id
    assert undo.expected_principal_operation_version == 1
    assert undo.expected_interest_operation_version == 1
    assert len(reader.detail_calls) == 1


def test_update_dispatches_safe_maintenance_command(app: FastAPI) -> None:
    app, reader, service, context = debts_app(app)
    debt_id = reader.detail.debt.account_id

    with TestClient(app) as client:
        response = client.put(
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

    assert response.status_code == 200
    assert service.update_calls == [
        (
            context.workspace,
            UpdateDebtCommand(
                debt_account_id=debt_id,
                name=" Кредит на ремонт ",
                opened_on=date(2026, 1, 1),
                maturity_date=date(2028, 1, 1),
                credit_limit=None,
                notes="Условия уточнены",
                expected_updated_at=NOW,
            ),
        )
    ]
    assert len(reader.detail_calls) == 1


def test_delete_dispatches_snapshot_and_returns_identity(app: FastAPI) -> None:
    app, reader, service, context = debts_app(app)
    debt_id = reader.detail.debt.account_id

    with TestClient(app) as client:
        response = client.request(
            "DELETE",
            f"/api/v1/debts/{debt_id}",
            json={"expectedUpdatedAt": NOW.isoformat()},
        )

    assert response.status_code == 200
    assert response.json() == {"deletedId": str(debt_id), "name": "Кредит"}
    assert service.delete_calls == [
        (
            context.workspace,
            DeleteDebtCommand(
                debt_account_id=debt_id,
                expected_updated_at=NOW,
            ),
        )
    ]


@pytest.mark.parametrize(
    ("method", "payload"),
    [
        pytest.param(
            "PUT",
            {
                "name": "Кредит",
                "openedOn": None,
                "maturityDate": None,
                "creditLimit": None,
                "notes": None,
                "expectedUpdatedAt": NOW.isoformat(),
            },
            id="update",
        ),
        pytest.param(
            "DELETE",
            {"expectedUpdatedAt": NOW.isoformat()},
            id="delete",
        ),
    ],
)
def test_debt_maintenance_requires_financial_write_permission(
    app: FastAPI,
    method: str,
    payload: dict[str, object],
) -> None:
    app, reader, service, _ = debts_app(app, role=WorkspaceRole.VIEWER)
    debt_id = reader.detail.debt.account_id

    with TestClient(app) as client:
        response = client.request(method, f"/api/v1/debts/{debt_id}", json=payload)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "financial_write_forbidden"
    assert service.update_calls == []
    assert service.delete_calls == []
    assert reader.detail_calls == []


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
    app: FastAPI,
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    app, reader, service, _ = debts_app(app)
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


def test_openapi_contains_debt_contracts(
    canonical_openapi_schema: dict[str, Any],
) -> None:
    paths = canonical_openapi_schema["paths"]

    assert "/api/v1/debts" in paths
    assert "/api/v1/debts/{debt_id}" in paths
    assert {"get", "put", "delete"} <= set(paths["/api/v1/debts/{debt_id}"])
    assert "/api/v1/debts/{debt_id}/payments" in paths
    assert "/api/v1/debts/{debt_id}/archive" in paths
    assert "/api/v1/debts/{debt_id}/restore" in paths
    assert "/api/v1/debt-payments/{payment_id}/undo" in paths
