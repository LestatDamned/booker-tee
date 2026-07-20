from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import ApiError, ApiErrorEnvelope
from app.api.v1.manual_ledger.mapper import (
    build_manual_ledger_response,
    manual_ledger_filter_options,
    manual_operation_response,
)
from app.api.v1.manual_ledger.mutation_errors import manual_ledger_mutation_error
from app.api.v1.manual_ledger.query import ManualLedgerQuery, parse_manual_ledger_query
from app.api.v1.manual_ledger.references import ManualLedgerReferenceReader
from app.api.v1.manual_ledger.schemas import (
    ManualLedgerListResponse,
    ManualOperationCreateRequest,
    ManualOperationEditResponse,
    ManualOperationLifecycleRequest,
    ManualOperationResponse,
    ManualOperationUpdateRequest,
    ManualTransferCreateRequest,
    ManualTransferUpdateRequest,
)
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.service import LedgerPostingService
from app.features.properties.service import PropertyService
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter(prefix="/manual-ledger", tags=["manual-ledger"])


def get_ledger_posting_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LedgerPostingService:
    return LedgerPostingService(session)


def get_manual_ledger_reference_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ManualLedgerReferenceReader:
    return ManualLedgerReferenceReader(
        accounts=AccountService(session),
        categories=CategoryService(session),
        properties=PropertyService(session),
    )


@router.get("", response_model=ManualLedgerListResponse)
async def list_manual_operations(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    query: Annotated[ManualLedgerQuery, Depends(parse_manual_ledger_query)],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
    reference_reader: Annotated[
        ManualLedgerReferenceReader,
        Depends(get_manual_ledger_reference_reader),
    ],
) -> ManualLedgerListResponse:
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
    return build_manual_ledger_response(
        operations=operations,
        page=page,
        references=references,
        can_write=can_write,
        target_operation_id=query.operation_id,
    )


@router.get(
    "/{operation_id}/edit",
    response_model=ManualOperationEditResponse,
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
) -> ManualOperationEditResponse:
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
    operation_response = manual_operation_response(operation, can_write=True)
    if not operation_response.capabilities.can_edit:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="operation_not_editable",
            message="Операцию в текущем состоянии нельзя редактировать.",
        )
    references = await reference_reader.read(context.workspace.workspace.id)
    return ManualOperationEditResponse(
        operation=operation_response,
        filter_options=manual_ledger_filter_options(references),
    )


@router.post(
    "",
    response_model=ManualOperationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ApiErrorEnvelope},
    },
)
async def create_manual_operation(
    request: ManualOperationCreateRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ManualOperationResponse:
    try:
        if isinstance(request, ManualTransferCreateRequest):
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

    operation = await ledger.get_manual_operation(
        workspace_id=context.workspace.workspace.id,
        operation_id=created.id,
    )
    if operation is None:
        raise RuntimeError("Created manual operation could not be reloaded.")
    return manual_operation_response(operation, can_write=True)


@router.put(
    "/{operation_id}",
    response_model=ManualOperationResponse,
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
    request: ManualOperationUpdateRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
) -> ManualOperationResponse:
    if isinstance(request, ManualTransferUpdateRequest):
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

    operation = await ledger.get_manual_operation(
        workspace_id=context.workspace.workspace.id,
        operation_id=updated.id,
    )
    if operation is None:
        raise RuntimeError("Updated manual operation could not be reloaded.")
    return manual_operation_response(operation, can_write=True)


@router.post(
    "/{operation_id}/cancel",
    response_model=ManualOperationResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
    },
)
async def cancel_manual_operation(
    operation_id: UUID,
    request: ManualOperationLifecycleRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
) -> ManualOperationResponse:
    try:
        cancelled = await ledger.cancel_manual_operation(
            context=context.workspace,
            operation_id=operation_id,
            expected_version=request.version,
        )
    except LedgerPostingError as error:
        raise manual_ledger_mutation_error(error) from error

    operation = await ledger.get_manual_operation(
        workspace_id=context.workspace.workspace.id,
        operation_id=cancelled.id,
    )
    if operation is None:
        raise RuntimeError("Cancelled manual operation could not be reloaded.")
    return manual_operation_response(operation, can_write=True)


@router.post(
    "/{operation_id}/restore",
    response_model=ManualOperationResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ApiErrorEnvelope},
        status.HTTP_403_FORBIDDEN: {"model": ApiErrorEnvelope},
        status.HTTP_404_NOT_FOUND: {"model": ApiErrorEnvelope},
        status.HTTP_409_CONFLICT: {"model": ApiErrorEnvelope},
    },
)
async def restore_manual_operation(
    operation_id: UUID,
    request: ManualOperationLifecycleRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[LedgerPostingService, Depends(get_ledger_posting_service)],
) -> ManualOperationResponse:
    try:
        restored = await ledger.restore_manual_operation(
            context=context.workspace,
            operation_id=operation_id,
            expected_version=request.version,
        )
    except LedgerPostingError as error:
        raise manual_ledger_mutation_error(error) from error

    operation = await ledger.get_manual_operation(
        workspace_id=context.workspace.workspace.id,
        operation_id=restored.id,
    )
    if operation is None:
        raise RuntimeError("Restored manual operation could not be reloaded.")
    return manual_operation_response(operation, can_write=True)


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
    request: ManualOperationLifecycleRequest,
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
