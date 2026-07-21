from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import ApiError, ApiErrorEnvelope
from app.api.v1.manual_ledger.dependencies import (
    get_ledger_posting_service,
    get_manual_ledger_reference_reader,
)
from app.api.v1.manual_ledger.mapper import ManualLedgerApiResponseMapper
from app.api.v1.manual_ledger.query import ManualLedgerQuery, parse_manual_ledger_query
from app.api.v1.manual_ledger.schemas.responses import (
    ManualLedgerListApiResponse,
    ManualOperationEditApiResponse,
)
from app.features.ledger.application.manual_operation_references import (
    ManualLedgerReferenceReader,
)
from app.features.ledger.service import LedgerPostingService
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter()


@router.get("", response_model=ManualLedgerListApiResponse)
async def list_manual_operations(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    query: Annotated[ManualLedgerQuery, Depends(parse_manual_ledger_query)],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
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

    operations, page = await ledger.list_manual_operations(
        context.workspace.workspace.id,
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
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
    },
)
async def load_manual_operation_edit(
    operation_id: UUID,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
    reference_reader: Annotated[
        ManualLedgerReferenceReader,
        Depends(get_manual_ledger_reference_reader),
    ],
) -> ManualOperationEditApiResponse:
    operation = await ledger.get_manual_operation(
        workspace_id=context.workspace.workspace.id,
        operation_id=operation_id,
    )
    if operation is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="manual_operation_not_found",
            message="Ручная операция не найдена.",
        )
    operation_response = ManualLedgerApiResponseMapper.operation_response(
        operation,
        can_write=True,
    )
    if not operation_response.capabilities.can_edit:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="operation_not_editable",
            message="Операцию в текущем состоянии нельзя редактировать.",
        )
    references = await reference_reader.read(context.workspace.workspace.id)
    return ManualOperationEditApiResponse(
        operation=operation_response,
        filter_options=ManualLedgerApiResponseMapper.filter_options(references),
    )
