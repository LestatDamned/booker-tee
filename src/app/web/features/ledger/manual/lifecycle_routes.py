from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.mapping.dto import ManualOperationView
from app.features.ledger.service import LedgerPostingService
from app.features.workspaces.dependencies import require_financial_write_context
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.forms import business_error_message
from app.web.features.ledger.manual.lifecycle_responses import (
    ManualLedgerLifecycleResponses,
)
from app.web.features.ledger.manual.query_state import (
    MANUAL_LEDGER_URL,
    safe_manual_ledger_return_to,
)
from app.web.features.ledger.manual.renderer import ManualLedgerRenderer
from app.web.templating import create_web_templates
from app.web.ui.responses import is_htmx_request

router = APIRouter()
renderer = ManualLedgerRenderer(create_web_templates())


@router.post("/{operation_id}/cancel")
async def cancel_manual_ledger_operation(
    request: Request,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    return_to: Annotated[str, Form()] = MANUAL_LEDGER_URL,
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(return_to)
    ledger = LedgerPostingService(session)
    previous = await ledger.get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
    )
    if previous is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await ledger.cancel_manual_operation(
            context=context,
            operation_id=operation_id,
        )
    except LedgerPostingError as error:
        return await _lifecycle_error_response(
            request,
            ledger=ledger,
            operation=previous,
            return_to=safe_return_to,
            error=error,
        )

    updated = await ledger.get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return await ManualLedgerLifecycleResponses(
        ledger=ledger,
        renderer=renderer,
    ).status_changed(
        request,
        context=context,
        previous=previous,
        updated=updated,
        return_to=safe_return_to,
    )


@router.post("/{operation_id}/restore")
async def restore_manual_ledger_operation(
    request: Request,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    return_to: Annotated[str, Form()] = MANUAL_LEDGER_URL,
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(return_to)
    ledger = LedgerPostingService(session)
    previous = await ledger.get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
    )
    if previous is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await ledger.restore_manual_operation(
            context=context,
            operation_id=operation_id,
        )
    except LedgerPostingError as error:
        return await _lifecycle_error_response(
            request,
            ledger=ledger,
            operation=previous,
            return_to=safe_return_to,
            error=error,
        )

    updated = await ledger.get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return await ManualLedgerLifecycleResponses(
        ledger=ledger,
        renderer=renderer,
    ).status_changed(
        request,
        context=context,
        previous=previous,
        updated=updated,
        return_to=safe_return_to,
    )


@router.post("/{operation_id}/delete")
async def delete_manual_ledger_operation(
    request: Request,
    operation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    context: Annotated[WorkspaceContext, Depends(require_financial_write_context)],
    return_to: Annotated[str, Form()] = MANUAL_LEDGER_URL,
) -> Response:
    safe_return_to = safe_manual_ledger_return_to(return_to)
    ledger = LedgerPostingService(session)
    operation = await ledger.get_manual_operation(
        workspace_id=context.workspace.id,
        operation_id=operation_id,
    )
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await ledger.delete_manual_operation(
            context=context,
            operation_id=operation_id,
        )
    except LedgerPostingError as error:
        return await _lifecycle_error_response(
            request,
            ledger=ledger,
            operation=operation,
            return_to=safe_return_to,
            error=error,
        )

    return await ManualLedgerLifecycleResponses(
        ledger=ledger,
        renderer=renderer,
    ).deleted(
        request,
        context=context,
        return_to=safe_return_to,
    )


async def _lifecycle_error_response(
    request: Request,
    *,
    ledger: LedgerPostingService,
    operation: ManualOperationView,
    return_to: str,
    error: LedgerPostingError,
) -> Response:
    message = business_error_message(error)
    if not is_htmx_request(request):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=message,
        ) from error
    return await ManualLedgerLifecycleResponses(
        ledger=ledger,
        renderer=renderer,
    ).error_row(
        request,
        operation=operation,
        return_to=return_to,
        message=message,
    )
