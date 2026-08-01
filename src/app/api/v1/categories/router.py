from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.categories.dependencies import get_category_directory_service
from app.api.v1.categories.schemas import (
    CategoryDirectoryApiResponse,
    CategorySummaryApiResponse,
    CreateCategoryApiRequest,
)
from app.features.categories.application.directory import CategoryDirectoryService
from app.features.categories.schemas import CreateCategoryCommand
from app.features.categories.service import CategoryError
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
