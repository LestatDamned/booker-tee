from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
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
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import OperationType
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/ledger", tags=["ledger"])
templates = create_templates()


@router.get("/manual", response_class=HTMLResponse)
async def manual_operation_form(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    accounts = await AccountService(session).list_or_create_default(
        context.workspace.id,
        context.workspace.default_currency,
    )
    categories = await CategoryService(session).list_or_seed_defaults(
        context.workspace.id,
        context.workspace.type,
    )
    properties = await PropertyService(session).list_active(context.workspace.id)
    manual_operations = await LedgerPostingService(session).list_manual_operations(
        context.workspace.id
    )
    return templates.TemplateResponse(
        request,
        "ledger/manual.html",
        {
            "accounts": accounts,
            "app_name": settings.app_name,
            "categories": categories,
            "manual_operations": manual_operations,
            "properties": properties,
            "workspace": context.workspace,
        },
    )


@router.post("/manual")
async def create_manual_operation(
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
    return f"/ledger/manual#operation-{operation_id}"
