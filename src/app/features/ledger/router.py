from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.application.listing import (
    LedgerPage,
    ManualOperationFilters,
    normalize_pagination,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationStatus, OperationType
from app.features.ledger.presentation.manual_operations.presenter import ManualOperationsPresenter
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    require_financial_write_context,
)
from app.features.workspaces.permissions import permission_flags_for
from app.features.workspaces.service import WorkspaceContext
from app.shared.query_params import (
    clean_optional_query_text,
    parse_optional_query_date,
    parse_optional_query_enum,
    parse_optional_query_uuid,
)
from app.templating import create_templates

router = APIRouter(prefix="/ledger", tags=["ledger"])
templates = create_templates()


@router.get("/manual", response_class=HTMLResponse)
async def manual_operation_form(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    operation_type_filter: Annotated[str | None, Query(alias="type")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    account_id: Annotated[str | None, Query()] = None,
    category_id: Annotated[str | None, Query()] = None,
    property_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    operation_id: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> HTMLResponse:
    filters = ManualOperationFilters(
        date_from=parse_optional_query_date(date_from, field_name="date_from"),
        date_to=parse_optional_query_date(date_to, field_name="date_to"),
        operation_type=parse_optional_query_enum(
            operation_type_filter,
            OperationType,
            field_name="type",
        ),
        status=parse_optional_query_enum(status_filter, OperationStatus, field_name="status"),
        account_id=parse_optional_query_uuid(account_id, field_name="account_id"),
        category_id=parse_optional_query_uuid(category_id, field_name="category_id"),
        property_id=parse_optional_query_uuid(property_id, field_name="property_id"),
        search=clean_optional_query_text(search),
    )
    focused_operation_id = parse_optional_query_uuid(operation_id, field_name="operation_id")
    accounts = await AccountService(session).list_active_accounts(context.workspace.id)
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
    )
    properties = await PropertyService(session).list_active(context.workspace.id)
    manual_operations, manual_page = await LedgerPostingService(session).list_manual_operations(
        context.workspace.id,
        filters=filters,
        pagination=normalize_pagination(page, per_page),
    )
    can_write = permission_flags_for(context.membership).can_write_financial_data
    manual_page_vm = ManualOperationsPresenter().build_page(
        operations=manual_operations,
        page=manual_page,
        filters=filters,
        focused_operation_id=focused_operation_id,
        can_write=can_write,
    )
    return templates.TemplateResponse(
        request,
        "ledger/manual.html",
        {
            "accounts": accounts,
            "app_name": settings.app_name,
            "categories": categories,
            "filters": filters,
            "focused_operation_id": focused_operation_id,
            "manual_operations": manual_operations,
            "manual_page": manual_page,
            "manual_page_vm": manual_page_vm,
            "operation_statuses": list(OperationStatus),
            "operation_types": list(OperationType),
            "page_urls": manual_operation_page_urls(
                filters,
                manual_page,
                operation_id=focused_operation_id,
            ),
            "properties": properties,
            "workspace": context.workspace,
        },
    )


@router.post("/manual")
async def create_manual_operation(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    operation_type: Annotated[OperationType, Form()],
    account_id: Annotated[UUID, Form()],
    amount: Annotated[Decimal, Form()],
    operation_date: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    category_id: Annotated[str | None, Form()] = None,
    property_id: Annotated[str | None, Form()] = None,
    destination_account_id: Annotated[str | None, Form()] = None,
) -> Response:
    service = LedgerPostingService(session)
    try:
        if operation_type == OperationType.TRANSFER:
            parsed_destination_account_id = parse_required_uuid(
                destination_account_id,
                "Destination account is required.",
            )
            operation = await service.create_manual_transfer(
                context=context,
                command=CreateManualTransferCommand(
                    source_account_id=account_id,
                    destination_account_id=parsed_destination_account_id,
                    amount=amount,
                    operation_date=parse_manual_operation_date(operation_date),
                    description=description,
                ),
            )
        else:
            operation = await service.create_manual_income_expense(
                context=context,
                command=CreateManualIncomeExpenseCommand(
                    operation_type=operation_type,
                    account_id=account_id,
                    amount=amount,
                    operation_date=parse_manual_operation_date(operation_date),
                    description=description,
                    category_id=parse_optional_uuid(category_id),
                    property_id=parse_optional_uuid(property_id),
                ),
            )
    except (ValueError, LedgerPostingError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedirectResponse(
        url=manual_operation_anchor_url(operation.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/manual/{operation_id}")
async def update_manual_operation(
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    operation_type: Annotated[OperationType, Form()],
    account_id: Annotated[UUID, Form()],
    amount: Annotated[Decimal, Form()],
    operation_date: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    category_id: Annotated[str | None, Form()] = None,
    property_id: Annotated[str | None, Form()] = None,
    destination_account_id: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        operation = await LedgerPostingService(session).update_manual_operation(
            context=context,
            command=UpdateManualOperationCommand(
                operation_id=operation_id,
                operation_type=operation_type,
                account_id=account_id,
                amount=amount,
                operation_date=parse_manual_operation_date(operation_date),
                description=description,
                category_id=parse_optional_uuid(category_id),
                property_id=parse_optional_uuid(property_id),
                destination_account_id=parse_optional_uuid(destination_account_id),
            ),
        )
    except (ValueError, LedgerPostingError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(
        url=manual_operation_anchor_url(operation.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/manual/{operation_id}/cancel")
async def cancel_manual_operation(
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    try:
        operation = await LedgerPostingService(session).cancel_manual_operation(
            context=context,
            operation_id=operation_id,
        )
    except LedgerPostingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(
        url=manual_operation_anchor_url(operation.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/manual/{operation_id}/restore")
async def restore_manual_operation(
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    try:
        operation = await LedgerPostingService(session).restore_manual_operation(
            context=context,
            operation_id=operation_id,
        )
    except LedgerPostingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(
        url=manual_operation_anchor_url(operation.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/manual/{operation_id}/delete")
async def delete_manual_operation(
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> Response:
    try:
        await LedgerPostingService(session).delete_manual_operation(
            context=context,
            operation_id=operation_id,
        )
    except LedgerPostingError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/ledger/manual", status_code=status.HTTP_303_SEE_OTHER)


def parse_optional_uuid(raw_value: str | None) -> UUID | None:
    if not raw_value:
        return None
    return UUID(raw_value)


def parse_required_uuid(raw_value: str | None, message: str) -> UUID:
    parsed = parse_optional_uuid(raw_value)
    if parsed is None:
        raise LedgerPostingError(message)
    return parsed


def parse_manual_operation_date(raw_value: str) -> date:
    cleaned = raw_value.strip()
    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    raise LedgerPostingError("Date must be in DD.MM.YYYY format.")


def manual_operation_anchor_url(operation_id: UUID) -> str:
    return f"/ledger/manual?operation_id={operation_id}#operation-{operation_id}"


def manual_operation_page_urls(
    filters: ManualOperationFilters,
    page: LedgerPage,
    *,
    operation_id: UUID | None,
) -> dict[str, str | None]:
    return {
        "previous": manual_operation_url(
            filters,
            page=page.previous_page,
            per_page=page.per_page,
            operation_id=operation_id,
        )
        if page.has_previous
        else None,
        "next": manual_operation_url(
            filters,
            page=page.next_page,
            per_page=page.per_page,
            operation_id=operation_id,
        )
        if page.has_next
        else None,
    }


def manual_operation_url(
    filters: ManualOperationFilters,
    *,
    page: int,
    per_page: int,
    operation_id: UUID | None = None,
) -> str:
    params = {
        "date_from": filters.date_from.isoformat() if filters.date_from else None,
        "date_to": filters.date_to.isoformat() if filters.date_to else None,
        "type": filters.operation_type.value if filters.operation_type else None,
        "status": filters.status.value if filters.status else None,
        "account_id": str(filters.account_id) if filters.account_id else None,
        "category_id": str(filters.category_id) if filters.category_id else None,
        "property_id": str(filters.property_id) if filters.property_id else None,
        "search": filters.search,
        "operation_id": str(operation_id) if operation_id else None,
        "page": page,
        "per_page": per_page,
    }
    query = urlencode({key: value for key, value in params.items() if value not in {None, ""}})
    return f"/ledger/manual?{query}"
