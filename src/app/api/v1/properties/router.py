from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import api_error_responses
from app.api.v1.properties.dependencies import get_property_directory_service
from app.api.v1.properties.schemas import PropertyDirectoryApiResponse
from app.features.properties.application.directory import PropertyDirectoryService
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
