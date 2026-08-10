from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.manual_ledger.dependencies import (
    get_manual_ledger_reference_reader,
    get_manual_operation_service,
)
from app.api.v1.manual_ledger.errors import manual_ledger_api_error
from app.api.v1.manual_ledger.mapping import (
    ManualLedgerResponseMapper,
    ManualOperationRequestMapper,
)
from app.api.v1.manual_ledger.schemas.list_parameters import (
    ManualLedgerListParameters,
    parse_manual_ledger_list_parameters,
)
from app.api.v1.manual_ledger.schemas.requests import (
    ManualOperationCreateApiRequest,
    ManualOperationLifecycleApiRequest,
    ManualOperationUpdateApiRequest,
)
from app.api.v1.manual_ledger.schemas.responses import (
    ManualLedgerListApiResponse,
    ManualOperationApiResponse,
    ManualOperationEditApiResponse,
)
from app.features.ledger.application.manual_operations import (
    ManualLedgerReferenceReader,
    ManualOperationService,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter(prefix="/manual-ledger", tags=["manual-ledger"])


@router.get(
    "",
    response_model=ManualLedgerListApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def list_manual_operations(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    parameters: Annotated[
        ManualLedgerListParameters,
        Depends(parse_manual_ledger_list_parameters),
    ],
    manual_operations: Annotated[
        ManualOperationService,
        Depends(get_manual_operation_service),
    ],
    reference_reader: Annotated[
        ManualLedgerReferenceReader,
        Depends(get_manual_ledger_reference_reader),
    ],
) -> ManualLedgerListApiResponse:
    if parameters.date_from and parameters.date_to and parameters.date_from > parameters.date_to:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_date_range",
            message="Начало периода не может быть позже конца периода.",
        )

    operations, page = await manual_operations.list(
        workspace_id=context.workspace.workspace.id,
        filters=parameters.filters,
        pagination=parameters.pagination,
    )
    target_operation = (
        await manual_operations.get(
            workspace_id=context.workspace.workspace.id,
            operation_id=parameters.operation_id,
        )
        if parameters.operation_id
        else None
    )
    references = await reference_reader.read(context.workspace.workspace.id)
    can_write = permission_flags_for(context.workspace.membership).can_write_financial_data
    return ManualLedgerResponseMapper.list_response(
        operations=operations,
        page=page,
        references=references,
        can_write=can_write,
        target_operation=target_operation,
    )


@router.get(
    "/{operation_id}/edit",
    response_model=ManualOperationEditApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def load_manual_operation_edit(
    operation_id: UUID,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    manual_operations: Annotated[
        ManualOperationService,
        Depends(get_manual_operation_service),
    ],
    reference_reader: Annotated[
        ManualLedgerReferenceReader,
        Depends(get_manual_ledger_reference_reader),
    ],
) -> ManualOperationEditApiResponse:
    try:
        operation = await manual_operations.get_for_edit(
            workspace_id=context.workspace.workspace.id,
            operation_id=operation_id,
        )
    except LedgerPostingError as error:
        raise manual_ledger_api_error(error) from error
    operation_response = ManualLedgerResponseMapper.operation_response(
        operation,
        can_write=True,
    )
    references = await reference_reader.read(context.workspace.workspace.id)
    return ManualOperationEditApiResponse(
        operation=operation_response,
        filter_options=ManualLedgerResponseMapper.filter_options(references),
    )


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
    command = ManualOperationRequestMapper.to_create_command(
        request,
        idempotency_key=idempotency_key,
    )
    try:
        operation = await manual_operations.create(context=context.workspace, command=command)
    except LedgerPostingError as error:
        raise manual_ledger_api_error(error) from error
    return ManualLedgerResponseMapper.operation_response(operation, can_write=True)


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
    command = ManualOperationRequestMapper.to_update_command(operation_id, request)
    try:
        operation = await manual_operations.update(context=context.workspace, command=command)
    except LedgerPostingError as error:
        raise manual_ledger_api_error(error) from error
    return ManualLedgerResponseMapper.operation_response(operation, can_write=True)


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
        raise manual_ledger_api_error(error) from error

    return ManualLedgerResponseMapper.operation_response(operation, can_write=True)


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
        raise manual_ledger_api_error(error) from error

    return ManualLedgerResponseMapper.operation_response(operation, can_write=True)


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
        raise manual_ledger_api_error(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
