import re
from datetime import date
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.categories.models import CategoryKind
from app.features.categories.presentation.presenter import (
    CategoryPagePresenter,
    categories_url,
    category_detail_url,
    category_form_error_message,
    category_form_state,
    category_recent_url,
    normalize_category_view,
)
from app.features.categories.service import CategoryError, CategoryService
from app.features.ledger.domain.types import OperationType
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
    recent_category_id: Annotated[UUID | None, Query()] = None,
) -> HTMLResponse:
    category_view = normalize_category_view(view)
    category_service = CategoryService(session)
    category_rows = await category_service.list_management_rows(
        context.workspace.id,
        context.workspace.type,
    )
    category_page = CategoryPagePresenter.build_index(
        category_rows,
        category_view=category_view,
        recent_category_id=recent_category_id,
    )
    return templates.TemplateResponse(
        request,
        "categories/index.html",
        {
            "app_name": settings.app_name,
            "category_page": category_page,
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
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    currency: Annotated[str | None, Query()] = None,
    operation_type: Annotated[str | None, Query(alias="type")] = None,
    return_to: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    parsed_date_from = parse_optional_query_date(date_from, field_name="date_from")
    parsed_date_to = parse_optional_query_date(date_to, field_name="date_to")
    parsed_currency = parse_optional_currency(currency) or context.workspace.default_currency
    parsed_operation_type = parse_optional_operation_type(operation_type)
    parsed_return_to = safe_reports_return_path(return_to)
    category_service = CategoryService(session)
    try:
        detail = await category_service.get_detail(
            workspace_id=context.workspace.id,
            category_id=category_id,
            date_from=parsed_date_from,
            date_to=parsed_date_to,
            currency=parsed_currency,
            operation_type=parsed_operation_type,
        )
    except CategoryError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    category_page = CategoryPagePresenter.build_detail(
        detail,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
        currency=parsed_currency,
        operation_type=parsed_operation_type,
        return_to=parsed_return_to,
    )
    return templates.TemplateResponse(
        request,
        "categories/detail.html",
        {
            "app_name": settings.app_name,
            "category_page": category_page,
            "workspace": context.workspace,
        },
    )


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


def parse_optional_currency(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    normalized = raw_value.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="currency должна быть трёхбуквенным кодом.",
        )
    return normalized


def parse_optional_operation_type(raw_value: str | None) -> OperationType | None:
    if not raw_value:
        return None
    try:
        operation_type = OperationType(raw_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="type должен быть income или expense.",
        ) from exc
    if operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="type должен быть income или expense.",
        )
    return operation_type


def safe_reports_return_path(raw_value: str | None) -> str | None:
    if not raw_value or not raw_value.startswith("/"):
        return None
    parsed = urlsplit(raw_value)
    if parsed.scheme or parsed.netloc or parsed.path != "/app/reports":
        return None
    return parsed.geturl()


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
    category_service = CategoryService(session)
    try:
        category = await category_service.create_custom(
            workspace_id=context.workspace.id,
            name=name,
            kind=kind,
            notes=notes,
        )
    except CategoryError as exc:
        category_rows = await category_service.list_management_rows(
            context.workspace.id,
            context.workspace.type,
        )
        category_page = CategoryPagePresenter.build_index(
            category_rows,
            category_view=normalize_category_view(view),
            create_form=category_form_state(
                error=category_form_error_message(exc),
                name=name,
                kind=kind,
                notes=notes,
            ),
        )
        return templates.TemplateResponse(
            request,
            "categories/index.html",
            {
                "app_name": settings.app_name,
                "category_page": category_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=category_recent_url(category.id, view),
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
    category_service = CategoryService(session)
    try:
        await category_service.update_custom(
            workspace_id=context.workspace.id,
            category_id=category_id,
            name=name,
            kind=kind,
            notes=notes,
        )
    except CategoryError as exc:
        try:
            detail = await category_service.get_detail(
                workspace_id=context.workspace.id,
                category_id=category_id,
            )
        except CategoryError as detail_exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(detail_exc),
            ) from detail_exc
        category_page = CategoryPagePresenter.build_detail(
            detail,
            edit_form=category_form_state(
                error=category_form_error_message(exc),
                name=name,
                kind=kind,
                notes=notes,
            ),
        )
        return templates.TemplateResponse(
            request,
            "categories/detail.html",
            {
                "app_name": settings.app_name,
                "category_page": category_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=category_detail_url(category_id),
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
    category_service = CategoryService(session)
    try:
        await category_service.set_active(
            workspace_id=context.workspace.id,
            category_id=category_id,
            is_active=False,
        )
    except CategoryError as exc:
        try:
            detail = await category_service.get_detail(
                workspace_id=context.workspace.id,
                category_id=category_id,
            )
        except CategoryError as detail_exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(detail_exc),
            ) from detail_exc
        category_page = CategoryPagePresenter.build_detail(
            detail,
            lifecycle_error=str(exc),
        )
        return templates.TemplateResponse(
            request,
            "categories/detail.html",
            {
                "app_name": settings.app_name,
                "category_page": category_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=category_detail_url(category_id),
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
    category_service = CategoryService(session)
    try:
        await category_service.set_active(
            workspace_id=context.workspace.id,
            category_id=category_id,
            is_active=True,
        )
    except CategoryError as exc:
        try:
            detail = await category_service.get_detail(
                workspace_id=context.workspace.id,
                category_id=category_id,
            )
        except CategoryError as detail_exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(detail_exc),
            ) from detail_exc
        category_page = CategoryPagePresenter.build_detail(
            detail,
            lifecycle_error=str(exc),
        )
        return templates.TemplateResponse(
            request,
            "categories/detail.html",
            {
                "app_name": settings.app_name,
                "category_page": category_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=category_detail_url(category_id),
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
    category_service = CategoryService(session)
    try:
        await category_service.delete_archived_custom(
            workspace_id=context.workspace.id,
            category_id=category_id,
        )
    except CategoryError as exc:
        try:
            detail = await category_service.get_detail(
                workspace_id=context.workspace.id,
                category_id=category_id,
            )
        except CategoryError as detail_exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(detail_exc),
            ) from detail_exc
        category_page = CategoryPagePresenter.build_detail(
            detail,
            lifecycle_error=str(exc),
        )
        return templates.TemplateResponse(
            request,
            "categories/detail.html",
            {
                "app_name": settings.app_name,
                "category_page": category_page,
                "workspace": context.workspace,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        url=categories_url(view),
        status_code=status.HTTP_303_SEE_OTHER,
    )
