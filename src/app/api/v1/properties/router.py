from typing import Annotated
from uuid import UUID

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
    PropertyLifecycleApiRequest,
    PropertyLifecycleApiResponse,
    PropertySummaryApiResponse,
    UpdatePropertyApiRequest,
)
from app.features.properties.application.directory import PropertyDirectoryService
from app.features.properties.models import PropertyStatus
from app.features.properties.schemas import (
    CreatePropertyCommand,
    PropertyLifecycleCommand,
    UpdatePropertyCommand,
)
from app.features.properties.service import (
    PropertyError,
    PropertyLifecycleConflictError,
    PropertyNotFoundError,
    PropertyUpdateConflictError,
)
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


@router.post(
    "/{property_id}/archive",
    response_model=PropertyLifecycleApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def archive_property(
    property_id: UUID,
    request: PropertyLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        PropertyDirectoryService,
        Depends(get_property_directory_service),
    ],
) -> PropertyLifecycleApiResponse:
    return await _set_property_status(
        property_id=property_id,
        request=request,
        expected_status=PropertyStatus.ACTIVE,
        status_=PropertyStatus.ARCHIVED,
        context=context,
        directory=directory,
    )


@router.post(
    "/{property_id}/restore",
    response_model=PropertyLifecycleApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def restore_property(
    property_id: UUID,
    request: PropertyLifecycleApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    directory: Annotated[
        PropertyDirectoryService,
        Depends(get_property_directory_service),
    ],
) -> PropertyLifecycleApiResponse:
    return await _set_property_status(
        property_id=property_id,
        request=request,
        expected_status=PropertyStatus.ARCHIVED,
        status_=PropertyStatus.ACTIVE,
        context=context,
        directory=directory,
    )


async def _set_property_status(
    *,
    property_id: UUID,
    request: PropertyLifecycleApiRequest,
    expected_status: PropertyStatus,
    status_: PropertyStatus,
    context: ApiRequestContext,
    directory: PropertyDirectoryService,
) -> PropertyLifecycleApiResponse:
    if request.expected_status != expected_status:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="property_lifecycle_conflict",
            message="Состояние объекта уже изменилось. Обновите список.",
        )
    try:
        result = await directory.set_status(
            workspace_id=context.workspace.workspace.id,
            property_id=property_id,
            status=status_,
            command=PropertyLifecycleCommand(
                expected_status=request.expected_status,
                expected_updated_at=request.expected_updated_at,
            ),
        )
    except PropertyNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="property_not_found",
            message="Объект не найден.",
        ) from error
    except PropertyLifecycleConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="property_lifecycle_conflict",
            message="Объект уже изменился. Обновите список.",
        ) from error
    return PropertyLifecycleApiResponse.model_validate(result)


@router.put(
    "/{property_id}",
    response_model=PropertySummaryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_property(
    property_id: UUID,
    request: UpdatePropertyApiRequest,
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
        property_ = await directory.update(
            workspace_id=context.workspace.workspace.id,
            property_id=property_id,
            command=UpdatePropertyCommand(
                name=request.name,
                short_name=request.short_name,
                address=request.address,
                expected_updated_at=request.expected_updated_at,
            ),
        )
    except PropertyNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="property_not_found",
            message="Объект не найден.",
        ) from error
    except PropertyUpdateConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="property_update_conflict",
            message="Объект уже изменился. Загрузите актуальные данные.",
        ) from error
    except PropertyError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="property_validation_error",
            message=str(error),
        ) from error
    return PropertySummaryApiResponse.model_validate(property_)
