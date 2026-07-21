from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.dependencies import ApiRequestContext, require_api_financial_write_context
from app.api.errors import api_error_responses
from app.api.v1.manual_ledger.command_mapper import ManualLedgerApiCommandMapper
from app.api.v1.manual_ledger.dependencies import get_manual_operation_service
from app.api.v1.manual_ledger.mapper import ManualLedgerApiResponseMapper
from app.api.v1.manual_ledger.mutation_errors import manual_operation_api_error
from app.api.v1.manual_ledger.schemas.requests import (
    ManualOperationCreateApiRequest,
    ManualOperationLifecycleApiRequest,
    ManualOperationUpdateApiRequest,
)
from app.api.v1.manual_ledger.schemas.responses import ManualOperationApiResponse
from app.features.ledger.application.manual_operations import ManualOperationService
from app.features.ledger.errors import LedgerPostingError

router = APIRouter()


@router.post(
    "",
    response_model=ManualOperationApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_manual_operation(
    request: ManualOperationCreateApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    manual_operations: Annotated[
        ManualOperationService,
        Depends(get_manual_operation_service),
    ],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ManualOperationApiResponse:
    command = ManualLedgerApiCommandMapper.create(
        request,
        idempotency_key=idempotency_key,
    )
    try:
        operation = await manual_operations.create(context=context.workspace, command=command)
    except LedgerPostingError as error:
        raise manual_operation_api_error(error) from error
    return ManualLedgerApiResponseMapper.operation_response(operation, can_write=True)


@router.put(
    "/{operation_id}",
    response_model=ManualOperationApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_manual_operation(
    operation_id: UUID,
    request: ManualOperationUpdateApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    manual_operations: Annotated[
        ManualOperationService,
        Depends(get_manual_operation_service),
    ],
) -> ManualOperationApiResponse:
    command = ManualLedgerApiCommandMapper.update(operation_id, request)
    try:
        operation = await manual_operations.update(context=context.workspace, command=command)
    except LedgerPostingError as error:
        raise manual_operation_api_error(error) from error
    return ManualLedgerApiResponseMapper.operation_response(operation, can_write=True)


@router.post(
    "/{operation_id}/cancel",
    response_model=ManualOperationApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def cancel_manual_operation(
    operation_id: UUID,
    request: ManualOperationLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    manual_operations: Annotated[
        ManualOperationService,
        Depends(get_manual_operation_service),
    ],
) -> ManualOperationApiResponse:
    try:
        operation = await manual_operations.cancel(
            context=context.workspace,
            operation_id=operation_id,
            expected_version=request.version,
        )
    except LedgerPostingError as error:
        raise manual_operation_api_error(error) from error

    return ManualLedgerApiResponseMapper.operation_response(operation, can_write=True)


@router.post(
    "/{operation_id}/restore",
    response_model=ManualOperationApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def restore_manual_operation(
    operation_id: UUID,
    request: ManualOperationLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    manual_operations: Annotated[
        ManualOperationService,
        Depends(get_manual_operation_service),
    ],
) -> ManualOperationApiResponse:
    try:
        operation = await manual_operations.restore(
            context=context.workspace,
            operation_id=operation_id,
            expected_version=request.version,
        )
    except LedgerPostingError as error:
        raise manual_operation_api_error(error) from error

    return ManualLedgerApiResponseMapper.operation_response(operation, can_write=True)


@router.delete(
    "/{operation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def delete_manual_operation(
    operation_id: UUID,
    request: ManualOperationLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    manual_operations: Annotated[
        ManualOperationService,
        Depends(get_manual_operation_service),
    ],
) -> Response:
    try:
        await manual_operations.delete(
            context=context.workspace,
            operation_id=operation_id,
            expected_version=request.version,
        )
    except LedgerPostingError as error:
        raise manual_operation_api_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
