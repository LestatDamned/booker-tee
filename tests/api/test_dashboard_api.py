from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from manual_ledger_support import api_context

from api_client import ApiTestClient as TestClient
from app.api.dependencies import get_api_request_context
from app.api.v1.dashboard.router import get_dashboard_overview_reader
from app.features.dashboard.application.overview import (
    DashboardAccount,
    DashboardDocument,
    DashboardOnboarding,
    DashboardOverview,
)
from app.features.imports.documents.dto import (
    ImportDocumentAccountDto,
    ImportDocumentNextStepKind,
)
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.reports.repository import ReportMoneySummaryRow
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


class DashboardReaderStub:
    def __init__(self) -> None:
        self.workspace_id: UUID | None = None
        self.default_currency: str | None = None
        self.account_id = uuid4()
        self.document_id = uuid4()

    async def read(
        self,
        *,
        workspace_id: UUID,
        default_currency: str,
        can_upload: bool,
    ) -> DashboardOverview:
        self.workspace_id = workspace_id
        self.default_currency = default_currency
        assert can_upload is False
        return DashboardOverview(
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 5),
            summary=ReportMoneySummaryRow(
                currency="RUB",
                income=Decimal("125000.00"),
                expense=Decimal("65000.00"),
                profit=Decimal("60000.00"),
            ),
            accounts=[
                DashboardAccount(
                    id=self.account_id,
                    name="Основной",
                    currency="RUB",
                    balance=Decimal("9118.88"),
                )
            ],
            active_account_count=1,
            attention_documents=[self.document()],
            attention_document_count=1,
            recent_documents=[self.document()],
            onboarding=DashboardOnboarding(
                has_accounts=True,
                has_documents=True,
                has_confirmed_activity=False,
                is_complete=False,
            ),
        )

    def document(self) -> DashboardDocument:
        return DashboardDocument(
            id=self.document_id,
            filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            created_at=datetime(2026, 8, 5, tzinfo=UTC),
            account=ImportDocumentAccountDto(
                id=self.account_id,
                name="Основной",
                currency="RUB",
            ),
            reviewable_row_count=4,
            next_step_kind=ImportDocumentNextStepKind.REVIEW,
        )


def test_dashboard_api_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/dashboard")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_dashboard_api_returns_workspace_scoped_decimal_string_contract() -> None:
    app = create_app()
    context = api_context(role=WorkspaceRole.VIEWER)
    context.workspace.workspace.name = "Личные финансы"
    context.workspace.workspace.default_currency = "RUB"
    reader = DashboardReaderStub()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_dashboard_overview_reader] = lambda: reader

    with TestClient(app) as client:
        response = client.get("/api/v1/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspaceName"] == "Личные финансы"
    assert payload["period"] == {"start": "2026-08-01", "end": "2026-08-05"}
    assert payload["summary"] == {
        "currency": "RUB",
        "income": "125000.00",
        "expense": "65000.00",
        "profit": "60000.00",
    }
    assert payload["accounts"][0]["balance"] == "9118.88"
    assert payload["attention"]["items"][0]["nextStepKind"] == "review"
    assert payload["capabilities"] == {
        "canUpload": False,
        "canWriteFinancialData": False,
        "primaryAction": "reports",
    }
    assert reader.workspace_id == context.workspace.workspace.id
    assert reader.default_currency == "RUB"
