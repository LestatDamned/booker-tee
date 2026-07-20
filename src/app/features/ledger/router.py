from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

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
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationType
from app.features.ledger.presentation.manual_operations.presenter import ManualOperationsPresenter
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.dependencies import (
    require_financial_write_context,
)
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/ledger", tags=["ledger"])
templates = create_templates()


@router.get("/manual", response_class=HTMLResponse)
async def manual_operation_form(
    request: Request,
) -> RedirectResponse:
    target = "/app/ledger/manual"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


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


@router.get("/manual/{operation_id}/edit", response_class=HTMLResponse)
async def manual_operation_edit_panel(
    request: Request,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
) -> HTMLResponse:
    operation = await LedgerPostingService(session).get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
    )
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    accounts = await AccountService(session).list_active_accounts(context.workspace.id)
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
    )
    properties = await PropertyService(session).list_active(context.workspace.id)
    edit_panel = ManualOperationsPresenter().build_edit_panel(
        operation,
        can_write=True,
    )
    return templates.TemplateResponse(
        request,
        "ledger/manual/_edit_panel.html",
        {
            "accounts": accounts,
            "categories": categories,
            "edit_panel": edit_panel,
            "properties": properties,
        },
    )


@router.post("/manual/{operation_id}")
async def update_manual_operation(
    request: Request,
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
    if is_htmx(request):
        return await manual_operation_row_response(
            request=request,
            session=session,
            context=context,
            operation_id=operation.id,
        )
    return RedirectResponse(
        url=manual_operation_anchor_url(operation.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/manual/{operation_id}/cancel")
async def cancel_manual_operation(
    request: Request,
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
    if is_htmx(request):
        return await manual_operation_row_response(
            request=request,
            session=session,
            context=context,
            operation_id=operation.id,
        )
    return RedirectResponse(
        url=manual_operation_anchor_url(operation.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/manual/{operation_id}/restore")
async def restore_manual_operation(
    request: Request,
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
    if is_htmx(request):
        return await manual_operation_row_response(
            request=request,
            session=session,
            context=context,
            operation_id=operation.id,
        )
    return RedirectResponse(
        url=manual_operation_anchor_url(operation.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/manual/{operation_id}/delete")
async def delete_manual_operation(
    request: Request,
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
    if is_htmx(request):
        return Response(headers={"HX-Reswap": "delete"})
    return RedirectResponse(url="/app/ledger/manual", status_code=status.HTTP_303_SEE_OTHER)


async def manual_operation_row_response(
    *,
    request: Request,
    session: AsyncSession,
    context: WorkspaceContext,
    operation_id: UUID,
) -> HTMLResponse:
    operation = await LedgerPostingService(session).get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
    )
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    row = (
        ManualOperationsPresenter()
        .build_page(
            operations=[operation],
            page=LedgerPage(page=1, per_page=1, total=1),
            filters=ManualOperationFilters(),
            focused_operation_id=None,
            can_write=True,
        )
        .rows[0]
    )
    return templates.TemplateResponse(
        request,
        "ledger/manual/_row.html",
        {
            "can_write": True,
            "row": row,
        },
    )


def parse_optional_uuid(raw_value: str | None) -> UUID | None:
    if not raw_value:
        return None
    return UUID(raw_value)


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


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
    return f"/app/ledger/manual?operation_id={operation_id}#operation-{operation_id}"


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
    return f"/app/ledger/manual?{query}"
