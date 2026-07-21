from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.dependencies import ApiRequestContext, require_api_financial_write_context
from app.api.errors import ApiErrorEnvelope
from app.api.v1.manual_ledger.dependencies import get_ledger_posting_service
from app.api.v1.manual_ledger.mapper import ManualLedgerApiResponseMapper
from app.api.v1.manual_ledger.mutation_errors import manual_ledger_mutation_error
from app.api.v1.manual_ledger.schemas.requests import (
    ManualOperationCreateApiRequest,
    ManualOperationLifecycleApiRequest,
    ManualOperationUpdateApiRequest,
    ManualTransferCreateApiRequest,
    ManualTransferUpdateApiRequest,
)
from app.api.v1.manual_ledger.schemas.responses import ManualOperationApiResponse
from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.service import LedgerPostingService

router = APIRouter()


@router.post(
    "",
    response_model=ManualOperationApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ApiErrorEnvelope},
    },
)
async def create_manual_operation(
    request: ManualOperationCreateApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ManualOperationApiResponse:
    try:
        if isinstance(request, ManualTransferCreateApiRequest):
            created = await ledger.create_manual_transfer(
                context=context.workspace,
                command=CreateManualTransferCommand(
                    source_account_id=request.source_account_id,
                    destination_account_id=request.destination_account_id,
                    amount=request.decimal_amount,
                    operation_date=request.operation_date,
                    description=request.description,
                    idempotency_key=idempotency_key,
                ),
            )
        else:
            created = await ledger.create_manual_income_expense(
                context=context.workspace,
                command=CreateManualIncomeExpenseCommand(
                    operation_type=request.operation_type,
                    account_id=request.account_id,
                    amount=request.decimal_amount,
                    operation_date=request.operation_date,
                    description=request.description,
                    category_id=request.category_id,
                    property_id=request.property_id,
                    idempotency_key=idempotency_key,
                ),
            )
    except LedgerPostingError as error:
        raise manual_ledger_mutation_error(error) from error

    return await _reload_manual_operation(
        ledger=ledger,
        workspace_id=context.workspace.workspace.id,
        operation_id=created.id,
    )


@router.put(
    "/{operation_id}",
    response_model=ManualOperationApiResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ApiErrorEnvelope},
    },
)
async def update_manual_operation(
    operation_id: UUID,
    request: ManualOperationUpdateApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
) -> ManualOperationApiResponse:
    if isinstance(request, ManualTransferUpdateApiRequest):
        account_id = request.source_account_id
        destination_account_id: UUID | None = request.destination_account_id
        category_id = None
        property_id = None
    else:
        account_id = request.account_id
        destination_account_id = None
        category_id = request.category_id
        property_id = request.property_id

    try:
        updated = await ledger.update_manual_operation(
            context=context.workspace,
            command=UpdateManualOperationCommand(
                operation_id=operation_id,
                operation_type=request.operation_type,
                account_id=account_id,
                amount=request.decimal_amount,
                operation_date=request.operation_date,
                description=request.description,
                category_id=category_id,
                property_id=property_id,
                destination_account_id=destination_account_id,
                expected_version=request.version,
            ),
        )
    except LedgerPostingError as error:
        raise manual_ledger_mutation_error(error) from error

    return await _reload_manual_operation(
        ledger=ledger,
        workspace_id=context.workspace.workspace.id,
        operation_id=updated.id,
    )


@router.post(
    "/{operation_id}/cancel",
    response_model=ManualOperationApiResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
    },
)
async def cancel_manual_operation(
    operation_id: UUID,
    request: ManualOperationLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
) -> ManualOperationApiResponse:
    try:
        cancelled = await ledger.cancel_manual_operation(
            context=context.workspace,
            operation_id=operation_id,
            expected_version=request.version,
        )
    except LedgerPostingError as error:
        raise manual_ledger_mutation_error(error) from error

    return await _reload_manual_operation(
        ledger=ledger,
        workspace_id=context.workspace.workspace.id,
        operation_id=cancelled.id,
    )


@router.post(
    "/{operation_id}/restore",
    response_model=ManualOperationApiResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
    },
)
async def restore_manual_operation(
    operation_id: UUID,
    request: ManualOperationLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
) -> ManualOperationApiResponse:
    try:
        restored = await ledger.restore_manual_operation(
            context=context.workspace,
            operation_id=operation_id,
            expected_version=request.version,
        )
    except LedgerPostingError as error:
        raise manual_ledger_mutation_error(error) from error

    return await _reload_manual_operation(
        ledger=ledger,
        workspace_id=context.workspace.workspace.id,
        operation_id=restored.id,
    )


@router.delete(
    "/{operation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
    },
)
async def delete_manual_operation(
    operation_id: UUID,
    request: ManualOperationLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
) -> Response:
    try:
        await ledger.delete_manual_operation(
            context=context.workspace,
            operation_id=operation_id,
            expected_version=request.version,
        )
    except LedgerPostingError as error:
        raise manual_ledger_mutation_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _reload_manual_operation(
    *,
    ledger: LedgerPostingService,
    workspace_id: UUID,
    operation_id: UUID,
) -> ManualOperationApiResponse:
    operation = await ledger.get_manual_operation(
        workspace_id=workspace_id,
        operation_id=operation_id,
    )
    if operation is None:
        raise RuntimeError("Changed manual operation could not be reloaded.")
    return ManualLedgerApiResponseMapper.operation_response(operation, can_write=True)
