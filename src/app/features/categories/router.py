from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.categories.models import CategoryKind
from app.features.categories.service import CategoryError, CategoryManagementRow, CategoryService
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    require_financial_write_context,
)
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/categories", tags=["categories"])
templates = create_templates()

CATEGORY_VIEW_OPTIONS = [
    ("active", "активные"),
    ("archived", "архив"),
    ("system", "системные"),
    ("all", "все"),
]
CATEGORY_VIEW_VALUES = {value for value, _label in CATEGORY_VIEW_OPTIONS}


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
    create_error: str | None = None,
    create_name: str = "",
    create_kind: CategoryKind = CategoryKind.MIXED,
    create_notes: str = "",
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    category_rows = await CategoryService(session).list_management_rows(
        context.workspace.id,
        context.workspace.type,
    )
    user_category_rows, system_category_rows = split_category_rows(category_rows, category_view)
    return templates.TemplateResponse(
        request,
        "categories/index.html",
        {
            "app_name": settings.app_name,
            "category_view": category_view,
            "category_view_options": CATEGORY_VIEW_OPTIONS,
            "user_category_rows": user_category_rows,
            "system_category_rows": system_category_rows,
            "kinds": list(CategoryKind),
            "workspace": context.workspace,
            "create_error": create_error,
            "create_name": create_name,
            "create_kind": create_kind,
            "create_notes": create_notes,
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
    return templates.TemplateResponse(
        request,
        "categories/detail.html",
        {
            "app_name": settings.app_name,
            "detail": detail,
            "kinds": list(CategoryKind),
            "workspace": context.workspace,
            "edit_error": edit_error,
            "edit_name": edit_name,
            "edit_kind": edit_kind,
            "edit_notes": edit_notes,
            "lifecycle_error": lifecycle_error,
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
            create_error=category_form_error_message(exc),
            create_name=name,
            create_kind=kind,
            create_notes=notes or "",
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


def normalize_category_view(raw_view: str | None) -> str:
    if raw_view in CATEGORY_VIEW_VALUES:
        return raw_view
    return "active"


def categories_url(raw_view: str | None) -> str:
    category_view = normalize_category_view(raw_view)
    if category_view == "active":
        return "/categories"
    return f"/categories?view={category_view}"


def category_form_error_message(error: CategoryError) -> str:
    message = str(error)
    if message == "Category name is required.":
        return "Введите название категории."
    return message


def split_category_rows(
    category_rows: list[CategoryManagementRow],
    category_view: str,
) -> tuple[list[CategoryManagementRow], list[CategoryManagementRow]]:
    if category_view == "active":
        return (
            [row for row in category_rows if not row.category.is_system and row.category.is_active],
            [],
        )
    if category_view == "archived":
        return (
            [
                row
                for row in category_rows
                if not row.category.is_system and not row.category.is_active
            ],
            [],
        )
    if category_view == "system":
        return ([], [row for row in category_rows if row.category.is_system])
    return (
        [row for row in category_rows if not row.category.is_system],
        [row for row in category_rows if row.category.is_system],
    )
