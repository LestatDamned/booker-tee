from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.reports.application.overview import ReportingOverviewReader
from app.features.reports.repository import ReportsRepository


def get_reporting_overview_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReportingOverviewReader:
    return ReportingOverviewReader(ReportsRepository(session))
