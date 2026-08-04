from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.session.mapper import SessionApiResponseMapper
from app.api.v1.workspaces.dependencies import (
    get_workspace_creator,
    get_workspace_directory_reader,
    get_workspace_member_service,
    get_workspace_ownership_service,
    get_workspace_session_switcher,
    get_workspace_settings_service,
)
from app.api.v1.workspaces.schemas import (
    CreateWorkspaceApiRequest,
    CreateWorkspaceApiResponse,
    LeaveWorkspaceApiRequest,
    LeaveWorkspaceApiResponse,
    SelectWorkspaceApiRequest,
    SelectWorkspaceApiResponse,
    TransferWorkspaceOwnershipApiRequest,
    TransferWorkspaceOwnershipApiResponse,
    TransitionWorkspaceMemberApiRequest,
    UpdateWorkspaceMemberRoleApiRequest,
    UpdateWorkspaceSettingsApiRequest,
    WorkspaceAuthorityNavigationOutcomeApiResponse,
    WorkspaceDirectoryApiResponse,
    WorkspaceDirectoryItemApiResponse,
    WorkspaceMembersApiResponse,
    WorkspaceNavigationOutcomeApiResponse,
    WorkspaceSettingsApiResponse,
)
from app.features.workspaces.application.creation import WorkspaceCreator
from app.features.workspaces.application.directory import (
    WorkspaceDirectoryReader,
    workspace_directory_item,
)
from app.features.workspaces.application.members import WorkspaceMemberService
from app.features.workspaces.application.ownership import WorkspaceOwnershipService
from app.features.workspaces.application.settings import WorkspaceSettingsService
from app.features.workspaces.application.switching import WorkspaceSessionSwitcher
from app.features.workspaces.commands import (
    CreateWorkspaceCommand,
    LeaveWorkspaceCommand,
    TransferWorkspaceOwnershipCommand,
    TransitionWorkspaceMemberCommand,
    UpdateWorkspaceMemberRoleApiCommand,
    UpdateWorkspaceSettingsCommand,
)
from app.features.workspaces.errors import (
    WorkspaceError,
    WorkspaceIdempotencyConflictError,
    WorkspaceMemberConflictError,
    WorkspaceMemberTransitionError,
    WorkspaceNotFoundError,
    WorkspaceOwnershipTransferConflictError,
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


@router.get(
    "/{workspace_id}/members",
    response_model=WorkspaceMembersApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_workspace_members(
    workspace_id: UUID,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    member_service: Annotated[
        WorkspaceMemberService,
        Depends(get_workspace_member_service),
    ],
) -> WorkspaceMembersApiResponse:
    try:
        members = await member_service.read(
            actor_user_id=context.workspace.user.id,
            workspace_id=workspace_id,
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    return WorkspaceMembersApiResponse.model_validate(members)


@router.put(
    "/{workspace_id}/members/{member_id}/role",
    response_model=WorkspaceMembersApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_workspace_member_role(
    workspace_id: UUID,
    member_id: UUID,
    request: UpdateWorkspaceMemberRoleApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    member_service: Annotated[
        WorkspaceMemberService,
        Depends(get_workspace_member_service),
    ],
) -> WorkspaceMembersApiResponse:
    try:
        members = await member_service.update_role(
            actor_user_id=context.workspace.user.id,
            workspace_id=workspace_id,
            command=UpdateWorkspaceMemberRoleApiCommand(
                member_id=member_id,
                role=request.role,
                expected_updated_at=request.expected_updated_at,
            ),
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceMemberConflictError as error:
        raise _member_conflict(error) from error
    except WorkspaceMemberTransitionError as error:
        raise _member_transition_blocked(error) from error
    return WorkspaceMembersApiResponse.model_validate(members)


@router.post(
    "/{workspace_id}/members/{member_id}/disable",
    response_model=WorkspaceMembersApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def disable_workspace_member(
    workspace_id: UUID,
    member_id: UUID,
    request: TransitionWorkspaceMemberApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    member_service: Annotated[
        WorkspaceMemberService,
        Depends(get_workspace_member_service),
    ],
) -> WorkspaceMembersApiResponse:
    return await _transition_member(
        action="disable",
        workspace_id=workspace_id,
        member_id=member_id,
        request=request,
        actor_user_id=context.workspace.user.id,
        service=member_service,
    )


@router.post(
    "/{workspace_id}/members/{member_id}/reactivate",
    response_model=WorkspaceMembersApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def reactivate_workspace_member(
    workspace_id: UUID,
    member_id: UUID,
    request: TransitionWorkspaceMemberApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    member_service: Annotated[
        WorkspaceMemberService,
        Depends(get_workspace_member_service),
    ],
) -> WorkspaceMembersApiResponse:
    return await _transition_member(
        action="reactivate",
        workspace_id=workspace_id,
        member_id=member_id,
        request=request,
        actor_user_id=context.workspace.user.id,
        service=member_service,
    )


async def _transition_member(
    *,
    action: Literal["disable", "reactivate"],
    workspace_id: UUID,
    member_id: UUID,
    request: TransitionWorkspaceMemberApiRequest,
    actor_user_id: UUID,
    service: WorkspaceMemberService,
) -> WorkspaceMembersApiResponse:
    command = TransitionWorkspaceMemberCommand(
        member_id=member_id,
        expected_updated_at=request.expected_updated_at,
    )
    try:
        members = (
            await service.disable(
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
                command=command,
            )
            if action == "disable"
            else await service.reactivate(
                actor_user_id=actor_user_id,
                workspace_id=workspace_id,
                command=command,
            )
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceMemberConflictError as error:
        raise _member_conflict(error) from error
    except WorkspaceMemberTransitionError as error:
        raise _member_transition_blocked(error) from error
    return WorkspaceMembersApiResponse.model_validate(members)


def _member_conflict(error: WorkspaceMemberConflictError) -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        code="member_role_conflict",
        message=str(error),
    )


def _member_transition_blocked(error: WorkspaceMemberTransitionError) -> ApiError:
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="member_transition_blocked",
        message=str(error),
        details={"reasonCodes": error.reason_codes},
    )


@router.post(
    "/{workspace_id}/transfer-ownership",
    response_model=TransferWorkspaceOwnershipApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def transfer_workspace_ownership(
    workspace_id: UUID,
    request: TransferWorkspaceOwnershipApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    service: Annotated[
        WorkspaceOwnershipService,
        Depends(get_workspace_ownership_service),
    ],
) -> TransferWorkspaceOwnershipApiResponse:
    try:
        result = await service.transfer(
            actor=context.workspace.user,
            session_token=_session_token(context),
            workspace_id=workspace_id,
            command=TransferWorkspaceOwnershipCommand(
                recipient_member_id=request.recipient_member_id,
                expected_workspace_updated_at=request.expected_workspace_updated_at,
                expected_recipient_updated_at=request.expected_recipient_updated_at,
            ),
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceOwnershipTransferConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="ownership_transfer_conflict",
            message=str(error),
        ) from error
    except WorkspaceMemberTransitionError as error:
        raise _member_transition_blocked(error) from error
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
    return TransferWorkspaceOwnershipApiResponse(
        members=WorkspaceMembersApiResponse.model_validate(result.members),
        session=SessionApiResponseMapper.from_workspace_context(
            workspace_context,
            csrf_token=context.csrf_token,
        ),
        navigation_outcome=WorkspaceAuthorityNavigationOutcomeApiResponse(
            href=f"/app/workspaces/{workspace_id}/settings",
        ),
    )


@router.post(
    "/{workspace_id}/leave",
    response_model=LeaveWorkspaceApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def leave_workspace(
    workspace_id: UUID,
    request: LeaveWorkspaceApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    service: Annotated[
        WorkspaceOwnershipService,
        Depends(get_workspace_ownership_service),
    ],
) -> LeaveWorkspaceApiResponse:
    try:
        result = await service.leave(
            actor=context.workspace.user,
            session_token=_session_token(context),
            workspace_id=workspace_id,
            command=LeaveWorkspaceCommand(
                expected_member_updated_at=request.expected_member_updated_at,
                expected_current_workspace_id=request.expected_current_workspace_id,
            ),
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceMemberConflictError as error:
        raise _member_conflict(error) from error
    except WorkspaceSwitchConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="workspace_switch_conflict",
            message=str(error),
            details={"currentWorkspaceId": str(error.current_workspace_id)},
        ) from error
    except WorkspaceOwnershipTransferConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="ownership_transfer_conflict",
            message=str(error),
        ) from error
    except WorkspaceMemberTransitionError as error:
        if "last_owner_required" in error.reason_codes:
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="last_owner_required",
                message=str(error),
                details={"reasonCodes": error.reason_codes},
            ) from error
        raise _member_transition_blocked(error) from error
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
    return LeaveWorkspaceApiResponse(
        session=SessionApiResponseMapper.from_workspace_context(
            workspace_context,
            csrf_token=context.csrf_token,
        ),
        navigation_outcome=WorkspaceNavigationOutcomeApiResponse(),
    )
