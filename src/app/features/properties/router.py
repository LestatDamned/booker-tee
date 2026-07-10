from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.properties.models import PropertyStatus
from app.features.properties.presentation.presenter import (
    PropertiesPagePresenter,
    property_form_state,
)
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
    recent_property_id: Annotated[UUID | None, Query()] = None,
) -> HTMLResponse:
    property_service = PropertyService(session)
    properties = await property_service.list_all(context.workspace.id)
    property_page = PropertiesPagePresenter.build_index(
        properties,
        recent_property_id=recent_property_id,
    )
    return templates.TemplateResponse(
        request,
        "properties/index.html",
        {
            "app_name": settings.app_name,
            "property_page": property_page,
            "workspace": context.workspace,
        },
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
    property_service = PropertyService(session)
    try:
        property_ = await property_service.create(
            workspace_id=context.workspace.id,
            name=name,
            short_name=short_name,
            address=address,
        )
    except PropertyError as exc:
        properties = await property_service.list_all(context.workspace.id)
        property_page = PropertiesPagePresenter.build_index(
            properties,
            create_form=property_form_state(
                error=str(exc),
                name=name,
                short_name=short_name,
                address=address,
            ),
        )
        return templates.TemplateResponse(
            request,
            "properties/index.html",
            {
                "app_name": settings.app_name,
                "property_page": property_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=property_recent_url(property_.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


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
    property_service = PropertyService(session)
    try:
        property_ = await property_service.update(
            workspace_id=context.workspace.id,
            property_id=property_id,
            name=name,
            short_name=short_name,
            address=address,
        )
    except PropertyError as exc:
        properties = await property_service.list_all(context.workspace.id)
        target_property_exists = any(property_.id == property_id for property_ in properties)
        property_page = PropertiesPagePresenter.build_index(
            properties,
            edit_forms_by_property_id=(
                {
                    property_id: property_form_state(
                        error=str(exc),
                        name=name,
                        short_name=short_name,
                        address=address,
                    )
                }
                if target_property_exists
                else None
            ),
            lifecycle_error=None if target_property_exists else str(exc),
        )
        return templates.TemplateResponse(
            request,
            "properties/index.html",
            {
                "app_name": settings.app_name,
                "property_page": property_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=property_anchor_url(property_.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


def property_anchor_id(property_id: UUID) -> str:
    return f"property-{property_id}"


def property_recent_url(property_id: UUID) -> str:
    anchor_id = property_anchor_id(property_id)
    return f"/properties?recent_property_id={property_id}#{anchor_id}"


def property_anchor_url(property_id: UUID) -> str:
    return f"/properties#{property_anchor_id(property_id)}"


@router.post("/{property_id}/archive")
async def archive_property(
    property_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    property_service = PropertyService(session)
    try:
        property_ = await property_service.set_status(
            workspace_id=context.workspace.id,
            property_id=property_id,
            status=PropertyStatus.ARCHIVED,
        )
    except PropertyError as exc:
        properties = await property_service.list_all(context.workspace.id)
        property_page = PropertiesPagePresenter.build_index(
            properties,
            lifecycle_error=str(exc),
        )
        return templates.TemplateResponse(
            request,
            "properties/index.html",
            {
                "app_name": settings.app_name,
                "property_page": property_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=property_anchor_url(property_.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{property_id}/restore")
async def restore_property(
    property_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    property_service = PropertyService(session)
    try:
        property_ = await property_service.set_status(
            workspace_id=context.workspace.id,
            property_id=property_id,
            status=PropertyStatus.ACTIVE,
        )
    except PropertyError as exc:
        properties = await property_service.list_all(context.workspace.id)
        property_page = PropertiesPagePresenter.build_index(
            properties,
            lifecycle_error=str(exc),
        )
        return templates.TemplateResponse(
            request,
            "properties/index.html",
            {
                "app_name": settings.app_name,
                "property_page": property_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=property_anchor_url(property_.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )
