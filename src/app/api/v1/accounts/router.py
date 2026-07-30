from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.accounts.dependencies import (
    get_account_directory_service,
    get_account_ledger_reader,
    get_imported_operation_review_use_case,
)
from app.api.v1.accounts.detail_mapping import AccountDetailResponseMapper
from app.api.v1.accounts.detail_parameters import (
    AccountDetailParameters,
    parse_account_detail_parameters,
)
from app.api.v1.accounts.schemas import (
    AccountDetailApiResponse,
    AccountDirectoryApiResponse,
    AccountDirectoryCapabilitiesApiResponse,
    AccountLifecycleApiRequest,
    AccountMovementApiResponse,
    AccountSummaryApiResponse,
    AccountSummaryCapabilitiesApiResponse,
    CreateAccountApiRequest,
    UpdateAccountApiRequest,
    UpdateImportedOperationReviewFieldsApiRequest,
)
from app.api.v1.manual_ledger.dependencies import get_manual_ledger_reference_reader
from app.features.accounts.application.directory import AccountDirectoryService
from app.features.accounts.schemas import (
    AccountSummaryDto,
    CreateAccountCommand,
    UpdateAccountCommand,
)
from app.features.accounts.service import (
    AccountCurrencyConflictError,
    AccountError,
    AccountLifecycleConflictError,
    AccountNotFoundError,
    AccountUpdateConflictError,
)
from app.features.ledger.application.account_ledger import (
    AccountLedgerEntryView,
    AccountLedgerReader,
)
from app.features.ledger.application.imported_operations import (
    ImportedOperationReviewUseCase,
    UpdateImportedOperationReviewFieldsCommand,
)
from app.features.ledger.application.manual_operations import ManualLedgerReferenceReader
from app.features.ledger.errors import (
    ImportedOperationNotEditableError,
    ImportedOperationNotFoundError,
    LedgerPostingError,
    OperationVersionConflictError,
)
from app.features.workspaces.permissions import can_write_financial_data

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get(
    "/{account_id}",
    response_model=AccountDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_account_detail(
    account_id: UUID,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    parameters: Annotated[
        AccountDetailParameters,
        Depends(parse_account_detail_parameters),
    ],
    ledger: Annotated[AccountLedgerReader, Depends(get_account_ledger_reader)],
    references: Annotated[
        ManualLedgerReferenceReader,
        Depends(get_manual_ledger_reference_reader),
    ],
) -> AccountDetailApiResponse:
    if parameters.date_from and parameters.date_to and parameters.date_from > parameters.date_to:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_date_range",
            message="Начало периода не может быть позже конца периода.",
        )
    workspace_id = context.workspace.workspace.id
    detail = await ledger.get_detail(
        workspace_id=workspace_id,
        account_id=account_id,
        filters=parameters.filters,
        pagination=parameters.pagination,
    )
    if detail is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="account_not_found",
            message="Счёт не найден.",
        )
    return AccountDetailResponseMapper.response(
        detail,
        await references.read(workspace_id),
        can_write=can_write_financial_data(context.workspace.membership),
    )


@router.get(
    "",
    response_model=AccountDirectoryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def list_accounts(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    directory: Annotated[
        AccountDirectoryService,
        Depends(get_account_directory_service),
    ],
) -> AccountDirectoryApiResponse:
    result = await directory.read(
        workspace_id=context.workspace.workspace.id,
        can_create=can_write_financial_data(context.workspace.membership),
    )
    return AccountDirectoryApiResponse(
        items=[
            account_summary_response(
                item,
                can_write=can_write_financial_data(context.workspace.membership),
            )
            for item in result.items
        ],
        account_types=result.account_types,
        capabilities=AccountDirectoryCapabilitiesApiResponse.model_validate(result.capabilities),
    )


@router.post(
    "",
    response_model=AccountSummaryApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_account(
    request: CreateAccountApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        AccountDirectoryService,
        Depends(get_account_directory_service),
    ],
) -> AccountSummaryApiResponse:
    try:
        account = await directory.create(
            workspace_id=context.workspace.workspace.id,
            command=CreateAccountCommand(
                name=request.name,
                account_type=request.account_type,
                currency=request.currency,
                initial_balance=request.decimal_initial_balance,
            ),
        )
    except AccountError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="account_validation_error",
            message=str(error),
        ) from error
    return account_summary_response(account, can_write=True)


@router.put(
    "/{account_id}",
    response_model=AccountSummaryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_account(
    account_id: UUID,
    request: UpdateAccountApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        AccountDirectoryService,
        Depends(get_account_directory_service),
    ],
) -> AccountSummaryApiResponse:
    try:
        account = await directory.update(
            workspace_id=context.workspace.workspace.id,
            account_id=account_id,
            command=UpdateAccountCommand(
                name=request.name,
                account_type=request.account_type,
                currency=request.currency,
                initial_balance=request.decimal_initial_balance,
                expected_updated_at=request.expected_updated_at,
            ),
        )
    except AccountNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="account_not_found",
            message="Счёт не найден.",
        ) from error
    except AccountUpdateConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="account_update_conflict",
            message="Счёт уже изменился. Загрузите актуальные данные.",
        ) from error
    except AccountCurrencyConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="account_currency_conflict",
            message=(
                "Нельзя изменить валюту счёта с финансовой историей. "
                "Создайте новый счёт в нужной валюте."
            ),
        ) from error
    except AccountError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="account_validation_error",
            message=str(error),
        ) from error
    return account_summary_response(account, can_write=True)


@router.put(
    "/{account_id}/operations/{operation_id}/review-fields",
    response_model=AccountMovementApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_imported_operation_review_fields(
    account_id: UUID,
    operation_id: UUID,
    request: UpdateImportedOperationReviewFieldsApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    ledger: Annotated[AccountLedgerReader, Depends(get_account_ledger_reader)],
    use_case: Annotated[
        ImportedOperationReviewUseCase,
        Depends(get_imported_operation_review_use_case),
    ],
) -> AccountMovementApiResponse:
    workspace_id = context.workspace.workspace.id
    if (
        await ledger.get_imported_operation(
            workspace_id=workspace_id,
            operation_id=operation_id,
            account_id=account_id,
        )
        is None
    ):
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="account_operation_not_found",
            message="Импортированная операция не найдена на этом счёте.",
        )
    try:
        await use_case.update_review_fields(
            context=context.workspace,
            command=UpdateImportedOperationReviewFieldsCommand(
                operation_id=operation_id,
                expected_version=request.expected_version,
                category_id=request.category_id,
                property_id=request.property_id,
                description=request.description,
            ),
        )
    except ImportedOperationNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="account_operation_not_found",
            message="Импортированная операция не найдена на этом счёте.",
        ) from error
    except OperationVersionConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="operation_version_conflict",
            message="Операция уже изменилась. Загрузите актуальные данные.",
        ) from error
    except ImportedOperationNotEditableError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="operation_not_editable",
            message="Эту импортированную операцию больше нельзя исправить.",
        ) from error
    except (LedgerPostingError, ValueError) as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="operation_review_fields_invalid",
            message="Проверьте категорию, объект и описание операции.",
        ) from error

    committed = await ledger.get_imported_operation(
        workspace_id=workspace_id,
        operation_id=operation_id,
        account_id=account_id,
    )
    if committed is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="account_operation_not_found",
            message="Импортированная операция не найдена на этом счёте.",
        )
    money_entry = next(
        (entry for entry in committed.money_entries if entry.account_id == account_id),
        None,
    )
    if money_entry is None or money_entry.account is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="account_operation_not_found",
            message="Импортированная операция не найдена на этом счёте.",
        )
    return AccountDetailResponseMapper.movement_response(
        AccountLedgerEntryView(
            operation=committed,
            operation_id=committed.id,
            amount=money_entry.amount,
            currency=money_entry.account.currency,
        ),
        can_write=True,
    )


def account_summary_response(
    account: AccountSummaryDto,
    *,
    can_write: bool,
) -> AccountSummaryApiResponse:
    return AccountSummaryApiResponse(
        id=account.id,
        name=account.name,
        account_type=account.account_type,
        currency=account.currency,
        initial_balance=str(account.initial_balance),
        balance=str(account.balance),
        balance_direction=account.balance_direction,
        movement_count=account.movement_count,
        is_active=account.is_active,
        updated_at=account.updated_at,
        capabilities=AccountSummaryCapabilitiesApiResponse(
            can_archive=can_write and account.is_active,
            can_restore=can_write and not account.is_active,
        ),
    )


@router.post(
    "/{account_id}/archive",
    response_model=AccountSummaryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def archive_account(
    account_id: UUID,
    request: AccountLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        AccountDirectoryService,
        Depends(get_account_directory_service),
    ],
) -> AccountSummaryApiResponse:
    return await _set_account_active(
        account_id=account_id,
        request=request,
        expected_active=True,
        is_active=False,
        context=context,
        directory=directory,
    )


@router.post(
    "/{account_id}/restore",
    response_model=AccountSummaryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def restore_account(
    account_id: UUID,
    request: AccountLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        AccountDirectoryService,
        Depends(get_account_directory_service),
    ],
) -> AccountSummaryApiResponse:
    return await _set_account_active(
        account_id=account_id,
        request=request,
        expected_active=False,
        is_active=True,
        context=context,
        directory=directory,
    )


async def _set_account_active(
    *,
    account_id: UUID,
    request: AccountLifecycleApiRequest,
    expected_active: bool,
    is_active: bool,
    context: ApiRequestContext,
    directory: AccountDirectoryService,
) -> AccountSummaryApiResponse:
    if request.expected_active is not expected_active:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="account_state_conflict",
            message="Состояние счета уже изменилось. Обновите список.",
        )
    try:
        account = await directory.set_active(
            workspace_id=context.workspace.workspace.id,
            account_id=account_id,
            is_active=is_active,
            expected_active=request.expected_active,
            expected_updated_at=request.expected_updated_at,
        )
    except AccountNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="account_not_found",
            message="Счёт не найден.",
        ) from error
    except AccountLifecycleConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="account_state_conflict",
            message="Счёт уже изменился. Обновите список.",
        ) from error
    return account_summary_response(account, can_write=True)
