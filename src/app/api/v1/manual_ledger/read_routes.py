from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

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
from app.api.v1.manual_ledger.mapper import ManualLedgerApiResponseMapper
from app.api.v1.manual_ledger.mutation_errors import manual_operation_api_error
from app.api.v1.manual_ledger.query import ManualLedgerQuery, parse_manual_ledger_query
from app.api.v1.manual_ledger.schemas.responses import (
    ManualLedgerListApiResponse,
    ManualOperationEditApiResponse,
)
from app.features.ledger.application.manual_operations import (
    ManualLedgerReferenceReader,
    ManualOperationService,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter()


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
    query: Annotated[ManualLedgerQuery, Depends(parse_manual_ledger_query)],
    manual_operations: Annotated[
        ManualOperationService,
        Depends(get_manual_operation_service),
    ],
    reference_reader: Annotated[
        ManualLedgerReferenceReader,
        Depends(get_manual_ledger_reference_reader),
    ],
) -> ManualLedgerListApiResponse:
    if query.date_from and query.date_to and query.date_from > query.date_to:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_date_range",
            message="Начало периода не может быть позже конца периода.",
        )

    operations, page = await manual_operations.list(
        workspace_id=context.workspace.workspace.id,
        filters=query.filters,
        pagination=query.pagination,
    )
    references = await reference_reader.read(context.workspace.workspace.id)
    can_write = permission_flags_for(context.workspace.membership).can_write_financial_data
    return ManualLedgerApiResponseMapper.list_response(
        operations=operations,
        page=page,
        references=references,
        can_write=can_write,
        target_operation_id=query.operation_id,
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
        raise manual_operation_api_error(error) from error
    operation_response = ManualLedgerApiResponseMapper.operation_response(
        operation,
        can_write=True,
    )
    references = await reference_reader.read(context.workspace.workspace.id)
    return ManualOperationEditApiResponse(
        operation=operation_response,
        filter_options=ManualLedgerApiResponseMapper.filter_options(references),
    )
