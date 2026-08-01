from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from manual_ledger_support import api_context

from api_client import ApiTestClient as TestClient
from app.api.dependencies import get_api_request_context
from app.api.v1.reports.dependencies import get_reporting_overview_reader
from app.api.v1.reports.router import uncategorized_operation
from app.features.ledger.domain.types import OperationSource, OperationType
from app.features.reports.application.overview import (
    ReportBalanceSummary,
    ReportingFilterError,
    ReportingFilterOptions,
    ReportingFilters,
    ReportingOverview,
    ReportingPagination,
)
from app.features.reports.repository import (
    ReportAccountBalanceRow,
    ReportCategoryAggregateRow,
    ReportFilterAccountRow,
    ReportFilterCategoryRow,
    ReportFilterPropertyRow,
    ReportMoneySummaryRow,
    ReportUncategorizedOperationRow,
    ReportUncategorizedPage,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


class ReportingReaderStub:
    def __init__(self) -> None:
        self.account_id = uuid4()
        self.category_id = uuid4()
        self.property_id = uuid4()
        self.document_id = uuid4()
        self.calls: list[tuple[UUID, str, ReportingFilters, ReportingPagination]] = []

    async def read(
        self,
        *,
        workspace_id: UUID,
        default_currency: str,
        filters: ReportingFilters,
        pagination: ReportingPagination = ReportingPagination(),
    ) -> ReportingOverview:
        self.calls.append((workspace_id, default_currency, filters, pagination))
        if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
            self.calls.clear()
            raise ReportingFilterError(
                "invalid_date_range",
                "Начало периода не может быть позже конца периода.",
            )
        if filters.property_id not in {None, self.property_id}:
            raise ReportingFilterError(
                "report_filter_not_found",
                "Фильтр недоступен в текущем workspace.",
            )
        applied = ReportingFilters(
            date_from=filters.date_from,
            date_to=filters.date_to,
            currency=filters.currency or default_currency,
            account_id=filters.account_id,
            category_id=filters.category_id,
            property_id=filters.property_id,
        )
        return ReportingOverview(
            filters=applied,
            filter_options=ReportingFilterOptions(
                accounts=[
                    ReportFilterAccountRow(self.account_id, "Основной", "RUB", True),
                    ReportFilterAccountRow(uuid4(), "Доллары", "USD", False),
                ],
                categories=[ReportFilterCategoryRow(self.category_id, "Продукты", True)],
                properties=[ReportFilterPropertyRow(self.property_id, "Квартира", True)],
                currencies=["RUB", "USD"],
            ),
            summary=ReportMoneySummaryRow(
                applied.currency or "",
                Decimal("100.00"),
                Decimal("40.00"),
                Decimal("60.00"),
            ),
            balance_summary=ReportBalanceSummary(
                currency=applied.currency or "",
                opening_balance=Decimal("1000.00"),
                closing_balance=Decimal("1060.00"),
                balance_change=Decimal("60.00"),
            ),
            account_balances=[
                ReportAccountBalanceRow(
                    account_id=self.account_id,
                    name="Основной",
                    currency="RUB",
                    opening_balance=Decimal("1000.00"),
                    closing_balance=Decimal("1060.00"),
                    balance_change=Decimal("60.00"),
                    is_active=True,
                )
            ],
            categories=[
                ReportCategoryAggregateRow(
                    self.category_id,
                    "Продукты",
                    applied.currency or "",
                    Decimal("0.00"),
                    Decimal("40.00"),
                    Decimal("-40.00"),
                    True,
                )
            ],
            properties=[],
            balance_as_of=applied.date_to,
            next_review_document_id=self.document_id,
            uncategorized=ReportUncategorizedPage(
                items=[
                    ReportUncategorizedOperationRow(
                        operation_id=uuid4(),
                        version=3,
                        operation_date=date(2026, 7, 15),
                        operation_type=OperationType.EXPENSE,
                        description="Кофе",
                        source=OperationSource.MANUAL,
                        signed_amount=Decimal("-250.00"),
                        currency=applied.currency or "",
                        account_id=self.account_id,
                    )
                ],
                page=pagination.page,
                page_size=pagination.page_size,
                total=1,
            ),
        )


def test_reports_api_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/reports")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_reports_api_returns_currency_safe_decimal_string_contract() -> None:
    app = create_app()
    context = api_context(role=WorkspaceRole.VIEWER)
    context.workspace.workspace.name = "Личные финансы"
    context.workspace.workspace.default_currency = "RUB"
    reader = ReportingReaderStub()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_reporting_overview_reader] = lambda: reader

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/reports?date_from=2026-07-01&date_to=2026-07-31"
            f"&currency=RUB&account_id={reader.account_id}"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspaceName"] == "Личные финансы"
    assert payload["appliedFilters"] == {
        "dateFrom": "2026-07-01",
        "dateTo": "2026-07-31",
        "currency": "RUB",
        "accountId": str(reader.account_id),
        "categoryId": None,
        "propertyId": None,
    }
    assert payload["summary"] == {
        "currency": "RUB",
        "income": "100.00",
        "expense": "40.00",
        "profit": "60.00",
    }
    assert payload["balanceSummary"] == {
        "currency": "RUB",
        "openingBalance": "1000.00",
        "closingBalance": "1060.00",
        "balanceChange": "60.00",
    }
    assert payload["accountBalances"][0] == {
        "accountId": str(reader.account_id),
        "name": "Основной",
        "currency": "RUB",
        "openingBalance": "1000.00",
        "closingBalance": "1060.00",
        "balanceChange": "60.00",
        "isActive": True,
    }
    assert payload["filterOptions"]["currencies"] == ["RUB", "USD"]
    assert payload["filterOptions"]["accounts"][1]["isActive"] is False
    assert payload["balanceAsOf"] == "2026-07-31"
    assert payload["nextReviewDocumentId"] == str(reader.document_id)
    assert payload["uncategorized"]["items"][0]["signedAmount"] == "-250.00"
    assert payload["uncategorized"]["items"][0]["capabilities"] == {
        "canCorrect": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }
    assert reader.calls[0][2].date_from == date(2026, 7, 1)


def test_reports_api_rejects_inverted_period_without_repository_reads() -> None:
    app = create_app()
    context = api_context(role=WorkspaceRole.OWNER)
    reader = ReportingReaderStub()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_reporting_overview_reader] = lambda: reader

    with TestClient(app) as client:
        response = client.get("/api/v1/reports?date_from=2026-08-01&date_to=2026-07-31")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_date_range"
    assert reader.calls == []


def test_reports_api_rejects_foreign_reference_without_financial_reads() -> None:
    app = create_app()
    context = api_context(role=WorkspaceRole.OWNER)
    reader = ReportingReaderStub()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_reporting_overview_reader] = lambda: reader

    with TestClient(app) as client:
        response = client.get(f"/api/v1/reports?property_id={uuid4()}")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "report_filter_not_found"
    assert len(reader.calls) == 1


def test_reports_api_rejects_invalid_query_shape() -> None:
    app = create_app()
    context = api_context(role=WorkspaceRole.OWNER)
    app.dependency_overrides[get_api_request_context] = lambda: context

    with TestClient(app) as client:
        response = client.get("/api/v1/reports?date_from=31.07.2026&currency=RU")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_report_filter"


def test_reports_api_accepts_bounded_uncategorized_pagination() -> None:
    app = create_app()
    context = api_context(role=WorkspaceRole.OWNER)
    reader = ReportingReaderStub()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_reporting_overview_reader] = lambda: reader

    with TestClient(app) as client:
        response = client.get("/api/v1/reports?uncategorized_page=3&uncategorized_page_size=25")

    assert response.status_code == 200
    assert reader.calls[0][3] == ReportingPagination(page=3, page_size=25)
    assert response.json()["uncategorized"]["items"][0]["capabilities"] == {
        "canCorrect": True,
        "readonlyReasonCode": None,
    }


@pytest.mark.parametrize(
    "query",
    [
        "uncategorized_page=0",
        "uncategorized_page=abc",
        "uncategorized_page_size=26",
    ],
)
def test_reports_api_rejects_invalid_uncategorized_pagination(query: str) -> None:
    app = create_app()
    context = api_context(role=WorkspaceRole.OWNER)
    app.dependency_overrides[get_api_request_context] = lambda: context

    with TestClient(app) as client:
        response = client.get(f"/api/v1/reports?{query}")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_report_filter"


@pytest.mark.parametrize(
    ("source", "account", "can_write", "expected_can_correct", "expected_reason"),
    [
        (OperationSource.MANUAL, None, True, True, None),
        (OperationSource.BANK_PDF, "account", True, True, None),
        (
            OperationSource.BANK_PDF,
            None,
            True,
            False,
            "correction_account_unavailable",
        ),
        (OperationSource.SYSTEM, None, True, False, "system_operation"),
        (
            OperationSource.MANUAL,
            None,
            False,
            False,
            "financial_write_forbidden",
        ),
    ],
)
def test_uncategorized_operation_capability_policy(
    source: OperationSource,
    account: str | None,
    can_write: bool,
    expected_can_correct: bool,
    expected_reason: str | None,
) -> None:
    response = uncategorized_operation(
        ReportUncategorizedOperationRow(
            operation_id=uuid4(),
            version=1,
            operation_date=date(2026, 7, 31),
            operation_type=OperationType.EXPENSE,
            description="Операция",
            source=source,
            signed_amount=Decimal("-10.00"),
            currency="RUB",
            account_id=uuid4() if account else None,
        ),
        can_write=can_write,
    )

    assert response.capabilities.can_correct is expected_can_correct
    assert response.capabilities.readonly_reason_code == expected_reason
