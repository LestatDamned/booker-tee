from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import api_error_responses
from app.api.v1.categories.dependencies import get_category_directory_service
from app.api.v1.categories.schemas import CategoryDirectoryApiResponse
from app.features.categories.application.directory import CategoryDirectoryService
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
