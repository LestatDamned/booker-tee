from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.properties.models import PropertyStatus
from app.features.properties.service import PropertyError, PropertyService
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    require_financial_write_context,
)
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
    return await property_index_response(
        request=request,
        session=session,
        settings=settings,
        context=context,
    )


async def property_index_response(
    *,
    request: Request,
    session: AsyncSession,
    settings: Settings,
    context: WorkspaceContext,
    create_error: str | None = None,
    create_name: str = "",
    create_short_name: str = "",
    create_address: str = "",
    edit_error_by_property_id: dict[UUID, str] | None = None,
    edit_values_by_property_id: dict[UUID, dict[str, str]] | None = None,
    lifecycle_error: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    properties = await PropertyService(session).list_all(context.workspace.id)
    return templates.TemplateResponse(
        request,
        "properties/index.html",
        {
            "app_name": settings.app_name,
            "properties": properties,
            "workspace": context.workspace,
            "create_error": create_error,
            "create_name": create_name,
            "create_short_name": create_short_name,
            "create_address": create_address,
            "edit_error_by_property_id": edit_error_by_property_id or {},
            "edit_values_by_property_id": edit_values_by_property_id or {},
            "lifecycle_error": lifecycle_error,
        },
        status_code=status_code,
    )


@router.post("")
async def create_property(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
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
        return await property_index_response(
            request=request,
            session=session,
            settings=settings,
            context=context,
            create_error=str(exc),
            create_name=name,
            create_short_name=short_name or "",
            create_address=address or "",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/properties", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{property_id}")
async def update_property(
    property_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
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
        return await property_index_response(
            request=request,
            session=session,
            settings=settings,
            context=context,
            edit_error_by_property_id={property_id: str(exc)},
            edit_values_by_property_id={
                property_id: {
                    "name": name,
                    "short_name": short_name or "",
                    "address": address or "",
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(url="/properties", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{property_id}/archive")
async def archive_property(
    property_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    try:
        await PropertyService(session).set_status(
            workspace_id=context.workspace.id,
            property_id=property_id,
            status=PropertyStatus.ARCHIVED,
        )
    except PropertyError as exc:
        return await property_index_response(
            request=request,
            session=session,
            settings=settings,
            context=context,
            lifecycle_error=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(url="/properties", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{property_id}/restore")
async def restore_property(
    property_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    try:
        await PropertyService(session).set_status(
            workspace_id=context.workspace.id,
            property_id=property_id,
            status=PropertyStatus.ACTIVE,
        )
    except PropertyError as exc:
        return await property_index_response(
            request=request,
            session=session,
            settings=settings,
            context=context,
            lifecycle_error=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(url="/properties", status_code=status.HTTP_303_SEE_OTHER)
