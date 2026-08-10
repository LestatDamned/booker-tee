from calendar import monthrange
from datetime import UTC, date, datetime
from re import fullmatch
from uuid import UUID

from app.features.reports.application.overview import (
    ReportingFilters,
    ReportingOverview,
    ReportingOverviewReader,
)
from app.features.reports.repository import ReportOperationEntryRow, ReportsRepository
from app.shared.schemas import ApplicationModel

MAX_MONTHLY_EXPORT_ENTRIES = 10_000


class MonthlyReportData(ApplicationModel):
    workspace_name: str
    month: str
    generated_at: datetime
    overview: ReportingOverview
    entries: list[ReportOperationEntryRow]


class InvalidReportMonthError(ValueError):
    pass


class MonthlyExportTooLargeError(ValueError):
    pass


class MonthlyReportReader:
    def __init__(
        self,
        overview_reader: ReportingOverviewReader,
        repository: ReportsRepository,
    ) -> None:
        self.overview_reader = overview_reader
        self.repository = repository

    async def read(
        self,
        *,
        workspace_id: UUID,
        workspace_name: str,
        default_currency: str,
        month: str,
        currency: str,
    ) -> MonthlyReportData:
        date_from, date_to = month_date_range(month)
        overview = await self.overview_reader.read(
            workspace_id=workspace_id,
            default_currency=default_currency,
            filters=ReportingFilters(
                date_from=date_from,
                date_to=date_to,
                currency=currency,
            ),
        )
        entries = await self.repository.list_operation_entries(
            workspace_id=workspace_id,
            filters=overview.filters,
            limit=MAX_MONTHLY_EXPORT_ENTRIES + 1,
        )
        if len(entries) > MAX_MONTHLY_EXPORT_ENTRIES:
            raise MonthlyExportTooLargeError
        return MonthlyReportData(
            workspace_name=workspace_name,
            month=month,
            generated_at=datetime.now(UTC),
            overview=overview,
            entries=entries,
        )


def month_date_range(value: str) -> tuple[date, date]:
    if fullmatch(r"\d{4}-\d{2}", value) is None:
        raise InvalidReportMonthError
    try:
        first = date.fromisoformat(f"{value}-01")
    except ValueError as error:
        raise InvalidReportMonthError from error
    return first, first.replace(day=monthrange(first.year, first.month)[1])
