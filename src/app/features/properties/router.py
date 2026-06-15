from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.properties.models import PropertyStatus
from app.features.properties.service import PropertyError, PropertyService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/properties", tags=["properties"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def property_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    properties = await PropertyService(session).list_all(context.workspace.id)
    return templates.TemplateResponse(
        request,
        "properties/index.html",
        {
            "app_name": settings.app_name,
            "properties": properties,
            "workspace": context.workspace,
        },
    )


@router.post("")
async def create_property(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    name: Annotated[str, Form()],
    short_name: Annotated[str | None, Form()] = None,
    address: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await PropertyService(session).create(
            workspace_id=context.workspace.id,
            name=name,
            short_name=short_name,
            address=address,
        )
    except PropertyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(url="/properties", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{property_id}")
async def update_property(
    property_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    name: Annotated[str, Form()],
    short_name: Annotated[str | None, Form()] = None,
    address: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await PropertyService(session).update(
            workspace_id=context.workspace.id,
            property_id=property_id,
            name=name,
            short_name=short_name,
            address=address,
        )
    except PropertyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(url="/properties", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{property_id}/archive")
async def archive_property(
    property_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    await PropertyService(session).set_status(
        workspace_id=context.workspace.id,
        property_id=property_id,
        status=PropertyStatus.ARCHIVED,
    )
    return RedirectResponse(url="/properties", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{property_id}/restore")
async def restore_property(
    property_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    await PropertyService(session).set_status(
        workspace_id=context.workspace.id,
        property_id=property_id,
        status=PropertyStatus.ACTIVE,
    )
    return RedirectResponse(url="/properties", status_code=status.HTTP_303_SEE_OTHER)
