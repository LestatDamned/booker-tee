from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import AccountType
from app.features.accounts.repository import AccountDirectoryRow
from app.features.dashboard.application.overview import DashboardOverviewReader
from app.features.imports.documents.dto import (
    ImportDocumentListFilters,
    ImportDocumentListPagination,
    ImportDocumentListRow,
    ImportDocumentListState,
    ImportDocumentListSummaryDto,
    ImportDocumentNextStepKind,
)
from app.features.imports.documents.types import ParseAttemptStatus, UploadedDocumentStatus
from app.features.reports.application.overview import ReportingFilters
from app.features.reports.repository import ReportMoneySummaryRow


class ReportSourceStub:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, ReportingFilters]] = []

    async def read_money_summary(
        self,
        *,
        workspace_id: UUID,
        filters: ReportingFilters,
    ) -> ReportMoneySummaryRow:
        self.calls.append((workspace_id, filters))
        return ReportMoneySummaryRow(
            currency=filters.currency or "",
            income=Decimal("125000.00"),
            expense=Decimal("65000.00"),
            profit=Decimal("60000.00"),
        )


class AccountSourceStub:
    def __init__(self) -> None:
        self.calls: list[UUID] = []
        self.rows = [account_row(index) for index in range(7)]
        self.rows.append(account_row(8, is_active=False))

    async def list_directory_rows(self, workspace_id: UUID) -> list[AccountDirectoryRow]:
        self.calls.append(workspace_id)
        return self.rows


class DocumentSourceStub:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, ImportDocumentListFilters, ImportDocumentListPagination]] = []
        self.attention = document_row(
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            total_row_count=0,
            latest_status=ParseAttemptStatus.REQUIRES_REVIEW,
        )
        self.recent = document_row(
            status=UploadedDocumentStatus.IMPORTED,
            total_row_count=4,
            latest_status=ParseAttemptStatus.SUCCESS,
        )

    async def list_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
        pagination: ImportDocumentListPagination,
    ) -> list[ImportDocumentListRow]:
        self.calls.append((workspace_id, filters, pagination))
        return (
            [self.attention]
            if filters.state is ImportDocumentListState.ATTENTION
            else [self.recent]
        )

    async def summarize_documents_for_workspace(
        self,
        workspace_id: UUID,
    ) -> ImportDocumentListSummaryDto:
        return ImportDocumentListSummaryDto(
            total_document_count=2,
            attention_document_count=1,
        )


@pytest.mark.asyncio
async def test_dashboard_reader_builds_bounded_workspace_overview() -> None:
    workspace_id = uuid4()
    reports = ReportSourceStub()
    accounts = AccountSourceStub()
    documents = DocumentSourceStub()

    overview = await DashboardOverviewReader(
        reports=reports,
        accounts=accounts,
        documents=documents,
    ).read(
        workspace_id=workspace_id,
        default_currency="rub",
        can_upload=True,
        today=date(2026, 8, 5),
    )

    assert overview.period_start == date(2026, 7, 1)
    assert overview.period_end == date(2026, 7, 31)
    assert overview.current_period_start == date(2026, 8, 1)
    assert overview.current_period_end == date(2026, 8, 5)
    assert reports.calls == [
        (
            workspace_id,
            ReportingFilters(
                date_from=date(2026, 7, 1),
                date_to=date(2026, 7, 31),
                currency="RUB",
            ),
        )
    ]
    assert accounts.calls == [workspace_id]
    assert len(overview.accounts) == 4
    assert overview.active_account_count == 7
    assert overview.accounts[0].balance == Decimal("110.00")
    assert overview.attention_document_count == 1
    assert overview.attention_documents[0].next_step_kind is ImportDocumentNextStepKind.MAPPING
    assert overview.recent_documents[0].next_step_kind is ImportDocumentNextStepKind.REVIEW
    assert overview.recent_documents[0].statement_period_end == date(2026, 8, 5)
    assert [call[2].per_page for call in documents.calls] == [3, 1]
    assert all(call[0] == workspace_id for call in documents.calls)
    assert overview.onboarding.has_confirmed_activity is True
    assert overview.onboarding.is_complete is False


@pytest.mark.asyncio
async def test_dashboard_onboarding_requires_an_active_account() -> None:
    accounts = AccountSourceStub()
    accounts.rows = [account_row(1, is_active=False)]

    overview = await DashboardOverviewReader(
        reports=ReportSourceStub(),
        accounts=accounts,
        documents=DocumentSourceStub(),
    ).read(
        workspace_id=uuid4(),
        default_currency="RUB",
        can_upload=True,
        today=date(2026, 8, 5),
    )

    assert overview.active_account_count == 0
    assert overview.onboarding.has_accounts is False
    assert overview.onboarding.is_complete is False


def account_row(index: int, *, is_active: bool = True) -> AccountDirectoryRow:
    return AccountDirectoryRow(
        id=uuid4(),
        name=f"Счёт {index}",
        account_type=AccountType.CARD,
        currency="RUB" if index % 2 == 0 else "USD",
        initial_balance=Decimal("100.00"),
        is_active=is_active,
        updated_at=datetime(2026, 8, 5, tzinfo=UTC),
        confirmed_entry_total=Decimal("10.00"),
        confirmed_movement_count=1,
    )


def document_row(
    *,
    status: UploadedDocumentStatus,
    total_row_count: int,
    latest_status: ParseAttemptStatus,
) -> ImportDocumentListRow:
    return ImportDocumentListRow(
        id=uuid4(),
        filename="statement.pdf",
        status=status,
        created_at=datetime(2026, 8, 5, tzinfo=UTC),
        file_size_bytes=1024,
        detected_bank_name="Bank",
        statement_period_start=date(2026, 8, 1),
        statement_period_end=date(2026, 8, 5),
        account_id=uuid4(),
        account_name="Основной",
        account_currency="RUB",
        account_bank_name="Bank",
        total_row_count=total_row_count,
        reviewable_row_count=total_row_count,
        latest_parse_attempt_status=latest_status,
    )
