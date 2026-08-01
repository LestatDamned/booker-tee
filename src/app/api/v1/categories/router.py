from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.categories.dependencies import (
    get_category_detail_reader,
    get_category_directory_service,
)
from app.api.v1.categories.parameters import (
    CategoryDetailParameters,
    parse_category_detail_parameters,
)
from app.api.v1.categories.schemas import (
    CategoryDeleteApiResponse,
    CategoryDetailApiResponse,
    CategoryDirectoryApiResponse,
    CategoryLifecycleApiRequest,
    CategoryLifecycleApiResponse,
    CategorySummaryApiResponse,
    CreateCategoryApiRequest,
    UpdateCategoryApiRequest,
)
from app.features.categories.application.detail import (
    CategoryDetailFilterError,
    CategoryDetailNotFoundError,
    CategoryDetailReader,
)
from app.features.categories.application.directory import CategoryDirectoryService
from app.features.categories.schemas import (
    CategoryDetailDto,
    CategoryLifecycleCommand,
    CreateCategoryCommand,
    UpdateCategoryCommand,
)
from app.features.categories.service import (
    CategoryArchiveBlockedError,
    CategoryDeleteBlockedError,
    CategoryError,
    CategoryLifecycleConflictError,
    CategoryNotFoundError,
    CategorySystemImmutableError,
    CategoryUpdateConflictError,
)
from app.features.workspaces.permissions import can_write_financial_data

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get(
    "",
    response_model=CategoryDirectoryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def list_categories(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    directory: Annotated[
        CategoryDirectoryService,
        Depends(get_category_directory_service),
    ],
) -> CategoryDirectoryApiResponse:
    result = await directory.read(
        workspace_id=context.workspace.workspace.id,
        workspace_type=context.workspace.workspace.type,
        can_write=can_write_financial_data(context.workspace.membership),
    )
    return CategoryDirectoryApiResponse.model_validate(result)


@router.post(
    "",
    response_model=CategorySummaryApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_category(
    request: CreateCategoryApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        CategoryDirectoryService,
        Depends(get_category_directory_service),
    ],
) -> CategorySummaryApiResponse:
    try:
        category = await directory.create(
            workspace_id=context.workspace.workspace.id,
            command=CreateCategoryCommand(
                name=request.name,
                kind=request.kind,
                notes=request.notes,
            ),
        )
    except CategoryError as error:
        field_errors = (
            {"name": [str(error)]}
            if str(error)
            in {
                "Category name is required.",
                "Категория с таким названием уже есть.",
            }
            else None
        )
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="category_validation_error",
            message=str(error),
            field_errors=field_errors,
        ) from error
    return CategorySummaryApiResponse.model_validate(category)


@router.get(
    "/{category_id}",
    response_model=CategoryDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_category_detail(
    category_id: UUID,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    parameters: Annotated[
        CategoryDetailParameters,
        Depends(parse_category_detail_parameters),
    ],
    reader: Annotated[
        CategoryDetailReader,
        Depends(get_category_detail_reader),
    ],
) -> CategoryDetailApiResponse:
    workspace = context.workspace.workspace
    try:
        detail = await reader.read(
            workspace_id=workspace.id,
            category_id=category_id,
            default_currency=workspace.default_currency,
            can_write=can_write_financial_data(context.workspace.membership),
            date_from=parameters.date_from,
            date_to=parameters.date_to,
            currency=parameters.currency,
            operation_type=parameters.operation_type,
            search=parameters.search,
            operations_page=parameters.operations_page,
            operations_page_size=parameters.operations_page_size,
        )
    except CategoryDetailNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="category_not_found",
            message="Категория не найдена.",
        ) from error
    except CategoryDetailFilterError as error:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=error.code,
            message=str(error),
        ) from error
    return category_detail_response(detail)


@router.put(
    "/{category_id}",
    response_model=CategoryDetailApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_category(
    category_id: UUID,
    request: UpdateCategoryApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    parameters: Annotated[
        CategoryDetailParameters,
        Depends(parse_category_detail_parameters),
    ],
    directory: Annotated[
        CategoryDirectoryService,
        Depends(get_category_directory_service),
    ],
    reader: Annotated[
        CategoryDetailReader,
        Depends(get_category_detail_reader),
    ],
) -> CategoryDetailApiResponse:
    workspace = context.workspace.workspace
    try:
        detail = await reader.read(
            workspace_id=workspace.id,
            category_id=category_id,
            default_currency=workspace.default_currency,
            can_write=True,
            date_from=parameters.date_from,
            date_to=parameters.date_to,
            currency=parameters.currency,
            operation_type=parameters.operation_type,
            search=parameters.search,
            operations_page=parameters.operations_page,
            operations_page_size=parameters.operations_page_size,
        )
        updated_category = await directory.update(
            workspace_id=workspace.id,
            category_id=category_id,
            command=UpdateCategoryCommand(
                name=request.name,
                kind=request.kind,
                notes=request.notes,
                expected_updated_at=request.expected_updated_at,
            ),
        )
        operation_count = updated_category.operation_count
        rule_count = updated_category.rule_count
        detail = detail.model_copy(
            update={
                "category": updated_category,
                "kind_change_impact": detail.kind_change_impact.model_copy(
                    update={
                        "operation_count": operation_count,
                        "rule_count": rule_count,
                        "requires_confirmation": (operation_count + rule_count) > 0,
                    }
                ),
            }
        )
    except (CategoryNotFoundError, CategoryDetailNotFoundError) as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="category_not_found",
            message="Категория не найдена.",
        ) from error
    except CategoryUpdateConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="category_update_conflict",
            message="Категория уже изменена. Загрузите актуальные данные.",
        ) from error
    except CategorySystemImmutableError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="category_system_immutable",
            message="Системную категорию нельзя изменить.",
        ) from error
    except CategoryError as error:
        field_errors = (
            {"name": [str(error)]}
            if str(error)
            in {
                "Category name is required.",
                "Категория с таким названием уже есть.",
            }
            else None
        )
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="category_validation_error",
            message=str(error),
            field_errors=field_errors,
        ) from error
    except CategoryDetailFilterError as error:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=error.code,
            message=str(error),
        ) from error
    return category_detail_response(detail)


@router.post(
    "/{category_id}/archive",
    response_model=CategoryLifecycleApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def archive_category(
    category_id: UUID,
    request: CategoryLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        CategoryDirectoryService,
        Depends(get_category_directory_service),
    ],
) -> CategoryLifecycleApiResponse:
    if request.expected_status is not True:
        raise category_lifecycle_conflict()
    return await change_category_lifecycle(
        category_id=category_id,
        request=request,
        is_active=False,
        context=context,
        directory=directory,
    )


@router.post(
    "/{category_id}/restore",
    response_model=CategoryLifecycleApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def restore_category(
    category_id: UUID,
    request: CategoryLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        CategoryDirectoryService,
        Depends(get_category_directory_service),
    ],
) -> CategoryLifecycleApiResponse:
    if request.expected_status is not False:
        raise category_lifecycle_conflict()
    return await change_category_lifecycle(
        category_id=category_id,
        request=request,
        is_active=True,
        context=context,
        directory=directory,
    )


async def change_category_lifecycle(
    *,
    category_id: UUID,
    request: CategoryLifecycleApiRequest,
    is_active: bool,
    context: ApiRequestContext,
    directory: CategoryDirectoryService,
) -> CategoryLifecycleApiResponse:
    try:
        result = await directory.set_active(
            workspace_id=context.workspace.workspace.id,
            category_id=category_id,
            is_active=is_active,
            command=CategoryLifecycleCommand(
                expected_status=request.expected_status,
                expected_updated_at=request.expected_updated_at,
            ),
        )
    except CategoryNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="category_not_found",
            message="Категория не найдена.",
        ) from error
    except CategoryLifecycleConflictError as error:
        raise category_lifecycle_conflict() from error
    except CategorySystemImmutableError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="category_system_immutable",
            message="Системную категорию нельзя изменить.",
        ) from error
    except CategoryArchiveBlockedError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="category_archive_blocked",
            message="Сначала отключите активные правила категории.",
            details={"activeRuleCount": error.active_rule_count},
        ) from error
    return CategoryLifecycleApiResponse.model_validate(result)


@router.delete(
    "/{category_id}",
    response_model=CategoryDeleteApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def delete_category(
    category_id: UUID,
    request: CategoryLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        CategoryDirectoryService,
        Depends(get_category_directory_service),
    ],
) -> CategoryDeleteApiResponse:
    if request.expected_status is not False:
        raise category_lifecycle_conflict()
    try:
        result = await directory.delete(
            workspace_id=context.workspace.workspace.id,
            category_id=category_id,
            command=CategoryLifecycleCommand(
                expected_status=request.expected_status,
                expected_updated_at=request.expected_updated_at,
            ),
        )
    except CategoryNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="category_not_found",
            message="Категория не найдена.",
        ) from error
    except CategoryLifecycleConflictError as error:
        raise category_lifecycle_conflict() from error
    except CategorySystemImmutableError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="category_system_immutable",
            message="Системную категорию нельзя удалить.",
        ) from error
    except CategoryDeleteBlockedError as error:
        blockers = error.dependencies
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="category_delete_blocked",
            message="Категория используется и не может быть удалена.",
            details={
                "operationCount": blockers.operation_count,
                "ruleCount": blockers.rule_count,
                "rawSuggestionCount": blockers.raw_suggestion_count,
                "childCategoryCount": blockers.child_category_count,
            },
        ) from error
    except CategoryError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="category_delete_blocked",
            message=str(error),
        ) from error
    return CategoryDeleteApiResponse.model_validate(result)


def category_lifecycle_conflict() -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        code="category_lifecycle_conflict",
        message="Категория уже изменена. Загрузите актуальные данные.",
    )


def category_detail_response(detail: CategoryDetailDto) -> CategoryDetailApiResponse:
    payload = detail.model_dump()
    summary = payload["summary"]
    for field in ("income", "expense", "profit"):
        summary[field] = decimal_string(summary[field])
    for operation in payload["operations"]["items"]:
        operation["signed_amount"] = decimal_string(operation["signed_amount"])
    return CategoryDetailApiResponse.model_validate(payload)


def decimal_string(value: Decimal) -> str:
    return f"{value:.2f}"
