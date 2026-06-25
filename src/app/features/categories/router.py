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
from app.features.workspaces.dependencies import get_current_workspace_context
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
        },
    )


@router.get("/{category_id}", response_class=HTMLResponse)
async def category_detail(
    category_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
        },
    )


@router.post("")
async def create_category(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{category_id}")
async def update_category(
    category_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{category_id}/archive")
async def archive_category(
    category_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    view: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await CategoryService(session).set_active(
            workspace_id=context.workspace.id,
            category_id=category_id,
            is_active=False,
        )
    except CategoryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{category_id}/restore")
async def restore_category(
    category_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    view: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        await CategoryService(session).set_active(
            workspace_id=context.workspace.id,
            category_id=category_id,
            is_active=True,
        )
    except CategoryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

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
