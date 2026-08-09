from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.debts.dependencies import get_debt_reader, get_debt_service
from app.api.v1.debts.errors import EXPECTED_DEBT_ERRORS, DebtApiErrors
from app.api.v1.debts.mapping import DebtRequestMapper, DebtResponseMapper
from app.api.v1.debts.schemas import (
    DebtCreateApiRequest,
    DebtDetailApiResponse,
    DebtLifecycleApiRequest,
    DebtPortfolioApiResponse,
    DeleteDebtApiRequest,
    DeleteDebtApiResponse,
    RecordDebtPaymentApiRequest,
    UndoDebtPaymentApiRequest,
    UpdateDebtApiRequest,
)
from app.features.debts.reader import DebtReader
from app.features.debts.schemas import (
    DebtLifecycleCommand,
    DeleteDebtCommand,
    UndoDebtPaymentCommand,
)
from app.features.debts.service import DebtService
from app.features.workspaces.permissions import can_write_financial_data

router = APIRouter()
debts_router = APIRouter(prefix="/debts", tags=["debts"])
payments_router = APIRouter(prefix="/debt-payments", tags=["debts"])


@debts_router.get(
    "",
    response_model=DebtPortfolioApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def list_debts(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[DebtReader, Depends(get_debt_reader)],
) -> DebtPortfolioApiResponse:
    can_write = can_write_financial_data(context.workspace.membership)
    portfolio = await reader.list(
        workspace_id=context.workspace.workspace.id,
        can_write=can_write,
    )
    return DebtResponseMapper.portfolio(portfolio, can_write=can_write)


@debts_router.get(
    "/{debt_id}",
    response_model=DebtDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def get_debt(
    debt_id: UUID,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[DebtReader, Depends(get_debt_reader)],
    payments_page: Annotated[int, Query(alias="paymentsPage", ge=1)] = 1,
    payments_page_size: Annotated[
        int,
        Query(alias="paymentsPageSize", ge=1, le=100),
    ] = 20,
) -> DebtDetailApiResponse:
    return await _read_detail(
        reader=reader,
        context=context,
        debt_id=debt_id,
        payments_page=payments_page,
        payments_page_size=payments_page_size,
    )


@debts_router.post(
    "",
    response_model=DebtDetailApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_debt(
    request: DebtCreateApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    service: Annotated[DebtService, Depends(get_debt_service)],
    reader: Annotated[DebtReader, Depends(get_debt_reader)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> DebtDetailApiResponse:
    command = DebtRequestMapper.to_create_command(request, idempotency_key=idempotency_key)
    try:
        debt = await service.create(context=context.workspace, command=command)
    except EXPECTED_DEBT_ERRORS as error:
        raise DebtApiErrors.from_exception(error) from error
    return await _read_detail(reader=reader, context=context, debt_id=debt.account_id)


@debts_router.put(
    "/{debt_id}",
    response_model=DebtDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_debt(
    debt_id: UUID,
    request: UpdateDebtApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    service: Annotated[DebtService, Depends(get_debt_service)],
    reader: Annotated[DebtReader, Depends(get_debt_reader)],
) -> DebtDetailApiResponse:
    try:
        await service.update(
            context=context.workspace,
            command=DebtRequestMapper.to_update_command(debt_id, request),
        )
    except EXPECTED_DEBT_ERRORS as error:
        raise DebtApiErrors.from_exception(error) from error
    return await _read_detail(reader=reader, context=context, debt_id=debt_id)


@debts_router.delete(
    "/{debt_id}",
    response_model=DeleteDebtApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def delete_debt(
    debt_id: UUID,
    request: DeleteDebtApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    service: Annotated[DebtService, Depends(get_debt_service)],
) -> DeleteDebtApiResponse:
    try:
        deleted = await service.delete(
            context=context.workspace,
            command=DeleteDebtCommand(
                debt_account_id=debt_id,
                expected_updated_at=request.expected_updated_at,
            ),
        )
    except EXPECTED_DEBT_ERRORS as error:
        raise DebtApiErrors.from_exception(error) from error
    return DeleteDebtApiResponse(deleted_id=deleted.account_id, name=deleted.name)


@debts_router.post(
    "/{debt_id}/payments",
    response_model=DebtDetailApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def record_debt_payment(
    debt_id: UUID,
    request: RecordDebtPaymentApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    service: Annotated[DebtService, Depends(get_debt_service)],
    reader: Annotated[DebtReader, Depends(get_debt_reader)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> DebtDetailApiResponse:
    try:
        await service.record_payment(
            context=context.workspace,
            command=DebtRequestMapper.to_payment_command(
                debt_id,
                request,
                idempotency_key=idempotency_key,
            ),
        )
    except EXPECTED_DEBT_ERRORS as error:
        raise DebtApiErrors.from_exception(error) from error
    return await _read_detail(reader=reader, context=context, debt_id=debt_id)


@debts_router.post(
    "/{debt_id}/archive",
    response_model=DebtDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def archive_debt(
    debt_id: UUID,
    request: DebtLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    service: Annotated[DebtService, Depends(get_debt_service)],
    reader: Annotated[DebtReader, Depends(get_debt_reader)],
) -> DebtDetailApiResponse:
    return await _change_lifecycle(
        action="archive",
        debt_id=debt_id,
        request=request,
        context=context,
        service=service,
        reader=reader,
    )


@debts_router.post(
    "/{debt_id}/restore",
    response_model=DebtDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def restore_debt(
    debt_id: UUID,
    request: DebtLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    service: Annotated[DebtService, Depends(get_debt_service)],
    reader: Annotated[DebtReader, Depends(get_debt_reader)],
) -> DebtDetailApiResponse:
    return await _change_lifecycle(
        action="restore",
        debt_id=debt_id,
        request=request,
        context=context,
        service=service,
        reader=reader,
    )


@payments_router.post(
    "/{payment_id}/undo",
    response_model=DebtDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def undo_debt_payment(
    payment_id: UUID,
    request: UndoDebtPaymentApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    service: Annotated[DebtService, Depends(get_debt_service)],
    reader: Annotated[DebtReader, Depends(get_debt_reader)],
) -> DebtDetailApiResponse:
    try:
        payment = await service.undo_payment(
            context=context.workspace,
            command=UndoDebtPaymentCommand(
                payment_id=payment_id,
                expected_principal_operation_version=(request.expected_principal_operation_version),
                expected_interest_operation_version=(request.expected_interest_operation_version),
            ),
        )
    except EXPECTED_DEBT_ERRORS as error:
        raise DebtApiErrors.from_exception(error) from error
    return await _read_detail(
        reader=reader,
        context=context,
        debt_id=payment.debt_account_id,
    )


async def _change_lifecycle(
    *,
    action: str,
    debt_id: UUID,
    request: DebtLifecycleApiRequest,
    context: ApiRequestContext,
    service: DebtService,
    reader: DebtReader,
) -> DebtDetailApiResponse:
    command = DebtLifecycleCommand(
        debt_account_id=debt_id,
        expected_active=request.expected_active,
        expected_updated_at=request.expected_updated_at,
    )
    try:
        if action == "archive":
            await service.archive(context=context.workspace, command=command)
        else:
            await service.restore(context=context.workspace, command=command)
    except EXPECTED_DEBT_ERRORS as error:
        raise DebtApiErrors.from_exception(error) from error
    return await _read_detail(reader=reader, context=context, debt_id=debt_id)


async def _read_detail(
    *,
    reader: DebtReader,
    context: ApiRequestContext,
    debt_id: UUID,
    payments_page: int = 1,
    payments_page_size: int = 20,
) -> DebtDetailApiResponse:
    detail = await reader.get_detail(
        workspace_id=context.workspace.workspace.id,
        account_id=debt_id,
        can_write=can_write_financial_data(context.workspace.membership),
        payments_page=payments_page,
        payments_page_size=payments_page_size,
    )
    if detail is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="debt_not_found",
            message="Долг не найден.",
        )
    return DebtResponseMapper.detail(detail)


router.include_router(debts_router)
router.include_router(payments_router)
