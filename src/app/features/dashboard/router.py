from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.dashboard.service import DashboardService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
templates = create_templates()


@router.get("/summary", response_class=HTMLResponse)
async def dashboard_summary(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    overview = await DashboardService(session).build_overview(context.workspace.id)
    return templates.TemplateResponse(
        request,
        "dashboard/summary.html",
        {
            "overview": overview,
            "workspace": context.workspace,
        },
    )
