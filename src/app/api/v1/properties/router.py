from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.properties.dependencies import get_property_directory_service
from app.api.v1.properties.schemas import (
    CreatePropertyApiRequest,
    PropertyDirectoryApiResponse,
    PropertySummaryApiResponse,
)
from app.features.properties.application.directory import PropertyDirectoryService
from app.features.properties.schemas import CreatePropertyCommand
from app.features.properties.service import PropertyError
from app.features.workspaces.permissions import can_write_financial_data

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get(
    "",
    response_model=PropertyDirectoryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def list_properties(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    directory: Annotated[
        PropertyDirectoryService,
        Depends(get_property_directory_service),
    ],
) -> PropertyDirectoryApiResponse:
    result = await directory.read(
        workspace_id=context.workspace.workspace.id,
        can_write=can_write_financial_data(context.workspace.membership),
    )
    return PropertyDirectoryApiResponse.model_validate(result)


@router.post(
    "",
    response_model=PropertySummaryApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_property(
    request: CreatePropertyApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        PropertyDirectoryService,
        Depends(get_property_directory_service),
    ],
) -> PropertySummaryApiResponse:
    try:
        property_ = await directory.create(
            workspace_id=context.workspace.workspace.id,
            command=CreatePropertyCommand(
                name=request.name,
                short_name=request.short_name,
                address=request.address,
            ),
        )
    except PropertyError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="property_validation_error",
            message=str(error),
        ) from error
    return PropertySummaryApiResponse.model_validate(property_)
