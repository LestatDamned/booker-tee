from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.session.mapper import SessionApiResponseMapper
from app.api.v1.workspaces.dependencies import (
    get_workspace_creator,
    get_workspace_directory_reader,
    get_workspace_session_switcher,
    get_workspace_settings_service,
)
from app.api.v1.workspaces.schemas import (
    CreateWorkspaceApiRequest,
    CreateWorkspaceApiResponse,
    SelectWorkspaceApiRequest,
    SelectWorkspaceApiResponse,
    UpdateWorkspaceSettingsApiRequest,
    WorkspaceDirectoryApiResponse,
    WorkspaceDirectoryItemApiResponse,
    WorkspaceNavigationOutcomeApiResponse,
    WorkspaceSettingsApiResponse,
)
from app.features.workspaces.application.creation import WorkspaceCreator
from app.features.workspaces.application.directory import (
    WorkspaceDirectoryReader,
    workspace_directory_item,
)
from app.features.workspaces.application.settings import WorkspaceSettingsService
from app.features.workspaces.application.switching import WorkspaceSessionSwitcher
from app.features.workspaces.commands import (
    CreateWorkspaceCommand,
    UpdateWorkspaceSettingsCommand,
)
from app.features.workspaces.errors import (
    WorkspaceError,
    WorkspaceIdempotencyConflictError,
    WorkspaceNotFoundError,
    WorkspaceSessionNotFoundError,
    WorkspaceSettingsForbiddenError,
    WorkspaceSwitchConflictError,
    WorkspaceUpdateConflictError,
)
from app.features.workspaces.service import WorkspaceContext

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get(
    "",
    response_model=WorkspaceDirectoryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def list_workspaces(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[WorkspaceDirectoryReader, Depends(get_workspace_directory_reader)],
) -> WorkspaceDirectoryApiResponse:
    directory = await reader.read_for_user(
        user_id=context.workspace.user.id,
        current_workspace_id=context.workspace.workspace.id,
    )
    return WorkspaceDirectoryApiResponse.model_validate(directory)


@router.post(
    "",
    response_model=CreateWorkspaceApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_workspace(
    request: CreateWorkspaceApiRequest,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    creator: Annotated[WorkspaceCreator, Depends(get_workspace_creator)],
) -> CreateWorkspaceApiResponse:
    try:
        result = await creator.create(
            actor=context.workspace.user,
            session_token=_session_token(context),
            command=CreateWorkspaceCommand(
                name=request.name,
                workspace_type=request.workspace_type,
                default_currency=request.default_currency,
            ),
            idempotency_key=idempotency_key,
        )
    except WorkspaceIdempotencyConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="idempotency_conflict",
            message=str(error),
        ) from error
    except WorkspaceSessionNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Требуется вход.",
        ) from error
    except WorkspaceError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="workspace_validation_error",
            message=str(error),
        ) from error
    workspace_context = WorkspaceContext(
        user=result.user,
        workspace=result.workspace,
        membership=result.membership,
    )
    return CreateWorkspaceApiResponse(
        workspace=WorkspaceDirectoryItemApiResponse.model_validate(
            workspace_directory_item(
                result.membership,
                current_workspace_id=result.workspace.id,
            )
        ),
        session=SessionApiResponseMapper.from_workspace_context(
            workspace_context,
            csrf_token=context.csrf_token,
        ),
        navigation_outcome=WorkspaceNavigationOutcomeApiResponse(),
        replayed=result.replayed,
    )


@router.post(
    "/{workspace_id}/select",
    response_model=SelectWorkspaceApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def select_workspace(
    workspace_id: UUID,
    request: SelectWorkspaceApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    switcher: Annotated[
        WorkspaceSessionSwitcher,
        Depends(get_workspace_session_switcher),
    ],
) -> SelectWorkspaceApiResponse:
    try:
        result = await switcher.switch(
            actor=context.workspace.user,
            session_token=_session_token(context),
            target_workspace_id=workspace_id,
            expected_current_workspace_id=request.expected_current_workspace_id,
        )
    except WorkspaceNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="workspace_not_found",
            message="Пространство больше недоступно.",
        ) from error
    except WorkspaceSwitchConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="workspace_switch_conflict",
            message=str(error),
            details={"currentWorkspaceId": str(error.current_workspace_id)},
        ) from error
    except WorkspaceSessionNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Требуется вход.",
        ) from error
    workspace_context = WorkspaceContext(
        user=result.user,
        workspace=result.workspace,
        membership=result.membership,
    )
    return SelectWorkspaceApiResponse(
        session=SessionApiResponseMapper.from_workspace_context(
            workspace_context,
            csrf_token=context.csrf_token,
        ),
        navigation_outcome=WorkspaceNavigationOutcomeApiResponse(),
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceSettingsApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_workspace_settings(
    workspace_id: UUID,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    settings_service: Annotated[
        WorkspaceSettingsService,
        Depends(get_workspace_settings_service),
    ],
) -> WorkspaceSettingsApiResponse:
    try:
        settings = await settings_service.read(
            actor_user_id=context.workspace.user.id,
            workspace_id=workspace_id,
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    return WorkspaceSettingsApiResponse.model_validate(settings)


@router.put(
    "/{workspace_id}",
    response_model=WorkspaceSettingsApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_workspace_settings(
    workspace_id: UUID,
    request: UpdateWorkspaceSettingsApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    settings_service: Annotated[
        WorkspaceSettingsService,
        Depends(get_workspace_settings_service),
    ],
) -> WorkspaceSettingsApiResponse:
    try:
        settings = await settings_service.update(
            actor_user_id=context.workspace.user.id,
            workspace_id=workspace_id,
            command=UpdateWorkspaceSettingsCommand(
                name=request.name,
                workspace_type=request.workspace_type,
                default_currency=request.default_currency,
                expected_updated_at=request.expected_updated_at,
            ),
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceSettingsForbiddenError as error:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="workspace_forbidden",
            message="Изменение настроек workspace недоступно.",
        ) from error
    except WorkspaceUpdateConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="workspace_update_conflict",
            message="Workspace уже изменён. Загрузите актуальные данные.",
        ) from error
    except WorkspaceError as error:
        field_errors = (
            {"name": [str(error)]}
            if "назван" in str(error).lower()
            else {"defaultCurrency": [str(error)]}
        )
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="workspace_validation_error",
            message=str(error),
            field_errors=field_errors,
        ) from error
    return WorkspaceSettingsApiResponse.model_validate(settings)


def _session_token(context: ApiRequestContext) -> str:
    if context.session_token is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Требуется вход.",
        )
    return context.session_token


def _workspace_not_found(error: WorkspaceNotFoundError) -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="workspace_not_found",
        message="Пространство не найдено.",
    )
