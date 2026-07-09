from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.categories.models import CategoryKind
from app.features.categories.presentation.models import CategoryFormStateVM
from app.features.categories.presentation.presenter import (
    CategoryPagePresenter,
    categories_url,
    category_form_error_message,
    category_form_state,
    normalize_category_view,
)
from app.features.categories.service import CategoryError, CategoryService
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    require_financial_write_context,
)
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
    view: Annotated[str, Query()] = "active",
) -> HTMLResponse:
    category_view = normalize_category_view(view)
    return await category_index_response(
        request=request,
        session=session,
        settings=settings,
        context=context,
        category_view=category_view,
    )


async def category_index_response(
    *,
    request: Request,
    session: AsyncSession,
    settings: Settings,
    context: WorkspaceContext,
    category_view: str,
    create_form: CategoryFormStateVM | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    category_rows = await CategoryService(session).list_management_rows(
        context.workspace.id,
        context.workspace.type,
    )
    category_page = CategoryPagePresenter.build_index(
        category_rows,
        category_view=category_view,
        create_form=create_form,
    )
    return templates.TemplateResponse(
        request,
        "categories/index.html",
        {
            "app_name": settings.app_name,
            "category_page": category_page,
            "workspace": context.workspace,
        },
        status_code=status_code,
    )


@router.get("/{category_id}", response_class=HTMLResponse)
async def category_detail(
    category_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    return await category_detail_response(
        category_id=category_id,
        request=request,
        session=session,
        settings=settings,
        context=context,
    )


async def category_detail_response(
    *,
    category_id: UUID,
    request: Request,
    session: AsyncSession,
    settings: Settings,
    context: WorkspaceContext,
    edit_error: str | None = None,
    edit_name: str | None = None,
    edit_kind: CategoryKind | None = None,
    edit_notes: str | None = None,
    lifecycle_error: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    try:
        detail = await CategoryService(session).get_detail(
            workspace_id=context.workspace.id,
            category_id=category_id,
        )
    except CategoryError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    category_page = CategoryPagePresenter.build_detail(
        detail,
        edit_form=(
            category_form_state(
                error=edit_error,
                name=edit_name,
                kind=edit_kind or detail.category.kind,
                notes=edit_notes,
            )
            if edit_error is not None and edit_name is not None
            else None
        ),
        lifecycle_error=lifecycle_error,
    )
    return templates.TemplateResponse(
        request,
        "categories/detail.html",
        {
            "app_name": settings.app_name,
            "category_page": category_page,
            "workspace": context.workspace,
        },
        status_code=status_code,
    )


@router.post("")
async def create_category(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    name: Annotated[str, Form()],
    kind: Annotated[CategoryKind, Form()] = CategoryKind.MIXED,
    notes: Annotated[str | None, Form()] = None,
    view: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await CategoryService(session).create_custom(
            workspace_id=context.workspace.id,
            name=name,
            kind=kind,
            notes=notes,
        )
    except CategoryError as exc:
        return await category_index_response(
            request=request,
            session=session,
            settings=settings,
            context=context,
            category_view=normalize_category_view(view),
            create_form=category_form_state(
                error=category_form_error_message(exc),
                name=name,
                kind=kind,
                notes=notes,
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{category_id}")
async def update_category(
    category_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    name: Annotated[str, Form()],
    kind: Annotated[CategoryKind, Form()],
    notes: Annotated[str | None, Form()] = None,
    view: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await CategoryService(session).update_custom(
            workspace_id=context.workspace.id,
            category_id=category_id,
            name=name,
            kind=kind,
            notes=notes,
        )
    except CategoryError as exc:
        return await category_detail_response(
            category_id=category_id,
            request=request,
            session=session,
            settings=settings,
            context=context,
            edit_error=category_form_error_message(exc),
            edit_name=name,
            edit_kind=kind,
            edit_notes=notes or "",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{category_id}/archive")
async def archive_category(
    category_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    view: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await CategoryService(session).set_active(
            workspace_id=context.workspace.id,
            category_id=category_id,
            is_active=False,
        )
    except CategoryError as exc:
        return await category_detail_response(
            category_id=category_id,
            request=request,
            session=session,
            settings=settings,
            context=context,
            lifecycle_error=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{category_id}/restore")
async def restore_category(
    category_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    view: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await CategoryService(session).set_active(
            workspace_id=context.workspace.id,
            category_id=category_id,
            is_active=True,
        )
    except CategoryError as exc:
        return await category_detail_response(
            category_id=category_id,
            request=request,
            session=session,
            settings=settings,
            context=context,
            lifecycle_error=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{category_id}/delete")
async def delete_category(
    category_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    view: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await CategoryService(session).delete_archived_custom(
            workspace_id=context.workspace.id,
            category_id=category_id,
        )
    except CategoryError as exc:
        return await category_detail_response(
            category_id=category_id,
            request=request,
            session=session,
            settings=settings,
            context=context,
            lifecycle_error=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )
