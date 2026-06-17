from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import UploadedDocument, UploadedDocumentStatus
from app.features.imports.query_repository import ImportQueryRepository
from app.features.reports.service import ReportFilters, ReportsOverview, ReportsService


@dataclass(frozen=True)
class DashboardOverview:
    reports: ReportsOverview
    month_start: date
    month_end: date
    documents_needing_review: list[UploadedDocument]
    recent_documents: list[UploadedDocument]


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.imports = ImportQueryRepository(session)
        self.reports = ReportsService(session)

    async def build_overview(
        self, workspace_id: UUID, today: date | None = None
    ) -> DashboardOverview:
        current_day = today or date.today()
        month_start = current_day.replace(day=1)
        month_end = current_day
        reports = await self.reports.build_overview(
            workspace_id=workspace_id,
            filters=ReportFilters(date_from=month_start, date_to=month_end),
        )
        documents = await self.imports.list_documents_for_workspace(workspace_id)
        return DashboardOverview(
            reports=reports,
            month_start=month_start,
            month_end=month_end,
            documents_needing_review=[
                document
                for document in documents
                if document.status
                in {
                    UploadedDocumentStatus.REQUIRES_REVIEW,
                    UploadedDocumentStatus.FAILED_TO_PARSE,
                    UploadedDocumentStatus.PENDING_PARSE,
                }
            ],
            recent_documents=documents[:5],
        )
