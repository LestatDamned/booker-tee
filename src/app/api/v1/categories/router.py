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
    CategoryDetailApiResponse,
    CategoryDirectoryApiResponse,
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
    CreateCategoryCommand,
    UpdateCategoryCommand,
)
from app.features.categories.service import (
    CategoryError,
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
