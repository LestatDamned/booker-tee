from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.workspaces.dependencies import get_workspace_activity_service
from app.api.v1.workspaces.schemas import WorkspaceActivityApiResponse
from app.features.workspaces.application.activity import WorkspaceActivityService
from app.features.workspaces.errors import (
    WorkspaceActivityForbiddenError,
    WorkspaceNotFoundError,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get(
    "/{workspace_id}/activity",
    response_model=WorkspaceActivityApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def get_workspace_activity(
    workspace_id: UUID,
    response: Response,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    service: Annotated[
        WorkspaceActivityService,
        Depends(get_workspace_activity_service),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_created_at: Annotated[
        datetime | None,
        Query(alias="beforeCreatedAt"),
    ] = None,
    before_id: Annotated[UUID | None, Query(alias="beforeId")] = None,
) -> WorkspaceActivityApiResponse:
    response.headers["Cache-Control"] = "no-store"
    if (before_created_at is None) != (before_id is None):
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_activity_cursor",
            message="Поля cursor должны передаваться вместе.",
        )
    try:
        activity = await service.read(
            actor_user_id=context.workspace.user.id,
            workspace_id=workspace_id,
            limit=limit,
            before_created_at=before_created_at,
            before_id=before_id,
        )
    except WorkspaceNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="workspace_not_found",
            message="Пространство не найдено.",
        ) from error
    except WorkspaceActivityForbiddenError as error:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="workspace_activity_forbidden",
            message=str(error),
        ) from error
    return WorkspaceActivityApiResponse.model_validate(activity)
