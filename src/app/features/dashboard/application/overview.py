from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.accounts.repository import AccountDirectoryRow
from app.features.imports.documents.dto import (
    ImportDocumentAccountDto,
    ImportDocumentListFilters,
    ImportDocumentListPagination,
    ImportDocumentListRow,
    ImportDocumentListState,
    ImportDocumentListSummaryDto,
    ImportDocumentNextStepKind,
)
from app.features.imports.documents.queries.list import import_document_item_from_row
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.reports.application.overview import ReportingFilters
from app.features.reports.repository import ReportMoneySummaryRow

DASHBOARD_ACCOUNT_LIMIT = 4
DASHBOARD_ATTENTION_LIMIT = 3
DASHBOARD_RECENT_DOCUMENT_LIMIT = 1


@dataclass(frozen=True)
class DashboardAccount:
    id: UUID
    name: str
    currency: str
    balance: Decimal


@dataclass(frozen=True)
class DashboardDocument:
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    created_at: datetime
    account: ImportDocumentAccountDto | None
    reviewable_row_count: int
    next_step_kind: ImportDocumentNextStepKind
    statement_period_end: date | None


@dataclass(frozen=True)
class DashboardOnboarding:
    has_accounts: bool
    has_documents: bool
    has_confirmed_activity: bool
    is_complete: bool


@dataclass(frozen=True)
class DashboardOverview:
    period_start: date
    period_end: date
    current_period_start: date
    current_period_end: date
    summary: ReportMoneySummaryRow
    accounts: list[DashboardAccount]
    active_account_count: int
    attention_documents: list[DashboardDocument]
    attention_document_count: int
    recent_documents: list[DashboardDocument]
    onboarding: DashboardOnboarding


class DashboardReportSource(Protocol):
    async def read_money_summary(
        self,
        *,
        workspace_id: UUID,
        filters: ReportingFilters,
    ) -> ReportMoneySummaryRow: ...


class DashboardAccountSource(Protocol):
    async def list_directory_rows(self, workspace_id: UUID) -> list[AccountDirectoryRow]: ...


class DashboardDocumentSource(Protocol):
    async def list_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
        pagination: ImportDocumentListPagination,
    ) -> list[ImportDocumentListRow]: ...

    async def summarize_documents_for_workspace(
        self,
        workspace_id: UUID,
    ) -> ImportDocumentListSummaryDto: ...


class DashboardOverviewReader:
    def __init__(
        self,
        *,
        reports: DashboardReportSource,
        accounts: DashboardAccountSource,
        documents: DashboardDocumentSource,
    ) -> None:
        self._reports = reports
        self._accounts = accounts
        self._documents = documents

    async def read(
        self,
        *,
        workspace_id: UUID,
        default_currency: str,
        can_upload: bool,
        today: date | None = None,
    ) -> DashboardOverview:
        current_day = today or date.today()
        current_period_start = current_day.replace(day=1)
        period_end = current_period_start - timedelta(days=1)
        period_start = period_end.replace(day=1)
        filters = ReportingFilters(
            date_from=period_start,
            date_to=period_end,
            currency=default_currency.upper(),
        )
        summary = await self._reports.read_money_summary(
            workspace_id=workspace_id,
            filters=filters,
        )
        account_rows = await self._accounts.list_directory_rows(workspace_id)
        document_summary = await self._documents.summarize_documents_for_workspace(workspace_id)
        attention_rows = await self._documents.list_document_rows_for_workspace(
            workspace_id=workspace_id,
            filters=ImportDocumentListFilters(state=ImportDocumentListState.ATTENTION),
            pagination=ImportDocumentListPagination(
                page=1,
                per_page=DASHBOARD_ATTENTION_LIMIT,
            ),
        )
        recent_rows = await self._documents.list_document_rows_for_workspace(
            workspace_id=workspace_id,
            filters=ImportDocumentListFilters(),
            pagination=ImportDocumentListPagination(
                page=1,
                per_page=DASHBOARD_RECENT_DOCUMENT_LIMIT,
            ),
        )
        active_accounts = [row for row in account_rows if row.is_active]
        has_confirmed_activity = any(row.confirmed_movement_count > 0 for row in account_rows)
        onboarding = DashboardOnboarding(
            has_accounts=bool(active_accounts),
            has_documents=document_summary.total_document_count > 0,
            has_confirmed_activity=has_confirmed_activity,
            is_complete=(
                bool(active_accounts)
                and document_summary.total_document_count > 0
                and document_summary.attention_document_count == 0
                and has_confirmed_activity
            ),
        )
        return DashboardOverview(
            period_start=period_start,
            period_end=period_end,
            current_period_start=current_period_start,
            current_period_end=current_day,
            summary=summary,
            accounts=[dashboard_account(row) for row in active_accounts[:DASHBOARD_ACCOUNT_LIMIT]],
            active_account_count=len(active_accounts),
            attention_documents=[
                dashboard_document(row, can_upload=can_upload) for row in attention_rows
            ],
            attention_document_count=document_summary.attention_document_count,
            recent_documents=[
                dashboard_document(row, can_upload=can_upload) for row in recent_rows
            ],
            onboarding=onboarding,
        )


def dashboard_account(row: AccountDirectoryRow) -> DashboardAccount:
    return DashboardAccount(
        id=row.id,
        name=row.name,
        currency=row.currency,
        balance=(row.initial_balance + row.confirmed_entry_total).quantize(Decimal("0.01")),
    )


def dashboard_document(
    row: ImportDocumentListRow,
    *,
    can_upload: bool,
) -> DashboardDocument:
    item = import_document_item_from_row(row, can_upload=can_upload)
    return DashboardDocument(
        id=item.id,
        filename=item.filename,
        status=item.status,
        created_at=item.created_at,
        account=item.account,
        reviewable_row_count=item.reviewable_row_count,
        next_step_kind=item.next_step_kind,
        statement_period_end=item.statement_period.end if item.statement_period else None,
    )
