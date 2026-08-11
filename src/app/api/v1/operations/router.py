from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.manual_ledger.dependencies import get_manual_ledger_reference_reader
from app.api.v1.operations.dependencies import get_operations_reader
from app.api.v1.operations.mapping import OperationsResponseMapper
from app.api.v1.operations.parameters import (
    OperationsListParameters,
    parse_operations_list_parameters,
)
from app.api.v1.operations.schemas import OperationsListApiResponse
from app.features.ledger.application.manual_operations import ManualLedgerReferenceReader
from app.features.ledger.application.operations import OperationsReader
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get(
    "",
    response_model=OperationsListApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def list_operations(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    parameters: Annotated[
        OperationsListParameters,
        Depends(parse_operations_list_parameters),
    ],
    operations: Annotated[OperationsReader, Depends(get_operations_reader)],
    reference_reader: Annotated[
        ManualLedgerReferenceReader,
        Depends(get_manual_ledger_reference_reader),
    ],
) -> OperationsListApiResponse:
    if parameters.date_from and parameters.date_to and parameters.date_from > parameters.date_to:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_date_range",
            message="Начало периода не может быть позже конца периода.",
        )
    workspace_id = context.workspace.workspace.id
    can_write = permission_flags_for(context.workspace.membership).can_write_financial_data
    items, page = await operations.list(
        workspace_id=workspace_id,
        can_write=can_write,
        filters=parameters.filters,
        pagination=parameters.pagination,
    )
    target_operation = (
        await operations.get(
            workspace_id=workspace_id,
            operation_id=parameters.operation_id,
            can_write=can_write,
        )
        if parameters.operation_id
        else None
    )
    references = await reference_reader.read(workspace_id)
    return OperationsResponseMapper.list_response(
        operations=items,
        page=page,
        references=references,
        can_write=can_write,
        target_operation=target_operation,
    )
