from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.properties.service import PropertyService
from app.features.reports.service import ReportFilters, ReportsService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/reports", tags=["reports"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def reports_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    account_id: Annotated[str | None, Query()] = None,
    category_id: Annotated[str | None, Query()] = None,
    property_id: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    filters = ReportFilters(
        date_from=parse_optional_query_date(date_from, field_name="date_from"),
        date_to=parse_optional_query_date(date_to, field_name="date_to"),
        account_id=parse_optional_query_uuid(account_id, field_name="account_id"),
        category_id=parse_optional_query_uuid(category_id, field_name="category_id"),
        property_id=parse_optional_query_uuid(property_id, field_name="property_id"),
    )
    accounts = await AccountService(session).list_or_create_default(
        context.workspace.id,
        context.workspace.default_currency,
    )
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
    )
    properties = await PropertyService(session).list_active(context.workspace.id)
    overview = await ReportsService(session).build_overview(
        workspace_id=context.workspace.id,
        filters=filters,
    )
    return templates.TemplateResponse(
        request,
        "reports/index.html",
        {
            "accounts": accounts,
            "app_name": settings.app_name,
            "categories": categories,
            "filters": filters,
            "overview": overview,
            "properties": properties,
            "workspace": context.workspace,
        },
    )


def parse_optional_query_uuid(raw_value: str | None, *, field_name: str) -> UUID | None:
    if not raw_value:
        return None
    try:
        return UUID(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} должен быть валидным UUID.",
        ) from exc


def parse_optional_query_date(raw_value: str | None, *, field_name: str) -> date | None:
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} должен быть датой в формате YYYY-MM-DD.",
        ) from exc
