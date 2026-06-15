from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.categories.models import CategoryKind
from app.features.categories.service import CategoryError, CategoryService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/categories", tags=["categories"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def category_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    categories = await CategoryService(session).list_or_seed_defaults(context.workspace.id)
    return templates.TemplateResponse(
        request,
        "categories/index.html",
        {
            "app_name": settings.app_name,
            "categories": categories,
            "kinds": list(CategoryKind),
            "workspace": context.workspace,
        },
    )


@router.post("")
async def create_category(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    name: Annotated[str, Form()],
    kind: Annotated[CategoryKind, Form()] = CategoryKind.MIXED,
) -> Response:
    try:
        await CategoryService(session).create_custom(
            workspace_id=context.workspace.id,
            name=name,
            kind=kind,
        )
    except CategoryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(url="/categories", status_code=status.HTTP_303_SEE_OTHER)
