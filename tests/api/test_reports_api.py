from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from manual_ledger_support import api_context

from api_client import ApiTestClient as TestClient
from app.api.dependencies import get_api_request_context
from app.api.v1.reports.dependencies import get_reporting_overview_reader
from app.features.reports.application.overview import (
    ReportingFilterError,
    ReportingFilterOptions,
    ReportingFilters,
    ReportingOverview,
)
from app.features.reports.repository import (
    ReportAccountBalanceRow,
    ReportCategoryAggregateRow,
    ReportFilterAccountRow,
    ReportFilterCategoryRow,
    ReportFilterPropertyRow,
    ReportMoneySummaryRow,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


class ReportingReaderStub:
    def __init__(self) -> None:
        self.account_id = uuid4()
        self.category_id = uuid4()
        self.property_id = uuid4()
        self.document_id = uuid4()
        self.calls: list[tuple[UUID, str, ReportingFilters]] = []

    async def read(
        self,
        *,
        workspace_id: UUID,
        default_currency: str,
        filters: ReportingFilters,
    ) -> ReportingOverview:
        self.calls.append((workspace_id, default_currency, filters))
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
            account_balances=[
                ReportAccountBalanceRow(
                    self.account_id,
                    "Основной",
                    "RUB",
                    Decimal("1060.00"),
                    True,
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
    assert payload["accountBalances"][0]["balance"] == "1060.00"
    assert payload["filterOptions"]["currencies"] == ["RUB", "USD"]
    assert payload["filterOptions"]["accounts"][1]["isActive"] is False
    assert payload["balanceAsOf"] == "2026-07-31"
    assert payload["nextReviewDocumentId"] == str(reader.document_id)
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
