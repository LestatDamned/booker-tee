from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Request, Response, status

from app.api.dependencies import (
    ApiRequestContext,
    AuthenticatedSessionContext,
    get_api_request_context,
    get_authenticated_session_context,
    require_api_member_directory_context,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.auth.dependencies import get_identity_email_sender
from app.api.v1.session.mapper import SessionApiResponseMapper
from app.api.v1.workspaces.dependencies import (
    get_workspace_creator,
    get_workspace_directory_reader,
    get_workspace_invitation_service,
    get_workspace_lifecycle_service,
    get_workspace_member_service,
    get_workspace_ownership_service,
    get_workspace_session_switcher,
    get_workspace_settings_service,
)
from app.api.v1.workspaces.schemas import (
    AcceptWorkspaceInvitationApiResponse,
    CreateWorkspaceApiRequest,
    CreateWorkspaceApiResponse,
    CreateWorkspaceInvitationApiRequest,
    CreateWorkspaceInvitationApiResponse,
    LeaveWorkspaceApiRequest,
    LeaveWorkspaceApiResponse,
    PublicWorkspaceInvitationApiResponse,
    RevokeWorkspaceInvitationApiRequest,
    SelectWorkspaceApiRequest,
    SelectWorkspaceApiResponse,
    TransferWorkspaceOwnershipApiRequest,
    TransferWorkspaceOwnershipApiResponse,
    TransitionWorkspaceLifecycleApiRequest,
    TransitionWorkspaceMemberApiRequest,
    UpdateWorkspaceMemberRoleApiRequest,
    UpdateWorkspaceSettingsApiRequest,
    WorkspaceAuthorityNavigationOutcomeApiResponse,
    WorkspaceDirectoryApiResponse,
    WorkspaceDirectoryItemApiResponse,
    WorkspaceInvitationItemApiResponse,
    WorkspaceInvitationsApiResponse,
    WorkspaceLifecycleApiResponse,
    WorkspaceLifecycleMutationImpactApiResponse,
    WorkspaceMembersApiResponse,
    WorkspaceNavigationOutcomeApiResponse,
    WorkspaceSettingsApiResponse,
)
from app.features.users.email_delivery import (
    IdentityEmailSender,
    build_workspace_invitation_message,
)
from app.features.users.errors import InvalidEmailError
from app.features.workspaces.application.creation import WorkspaceCreator
from app.features.workspaces.application.directory import (
    WorkspaceDirectoryReader,
    workspace_directory_item,
)
from app.features.workspaces.application.invitations import WorkspaceInvitationService
from app.features.workspaces.application.lifecycle import WorkspaceLifecycleService
from app.features.workspaces.application.members import WorkspaceMemberService
from app.features.workspaces.application.ownership import WorkspaceOwnershipService
from app.features.workspaces.application.settings import WorkspaceSettingsService
from app.features.workspaces.application.switching import WorkspaceSessionSwitcher
from app.features.workspaces.commands import (
    CreateWorkspaceCommand,
    LeaveWorkspaceCommand,
    TransferWorkspaceOwnershipCommand,
    TransitionWorkspaceLifecycleCommand,
    TransitionWorkspaceMemberCommand,
    UpdateWorkspaceMemberRoleApiCommand,
    UpdateWorkspaceSettingsCommand,
)
from app.features.workspaces.errors import (
    WorkspaceError,
    WorkspaceIdempotencyConflictError,
    WorkspaceInvitationConflictError,
    WorkspaceInvitationNotFoundError,
    WorkspaceInvitationTransitionError,
    WorkspaceLifecycleConflictError,
    WorkspaceLifecycleTransitionError,
    WorkspaceMemberConflictError,
    WorkspaceMemberDirectoryForbiddenError,
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
    "/invitations/{invitation_token}",
    response_model=PublicWorkspaceInvitationApiResponse,
    responses=api_error_responses(status.HTTP_404_NOT_FOUND),
)
async def preview_workspace_invitation(
    invitation_token: str,
    response: Response,
    service: Annotated[
        WorkspaceInvitationService,
        Depends(get_workspace_invitation_service),
    ],
) -> PublicWorkspaceInvitationApiResponse:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    try:
        invitation = await service.preview(invitation_token=invitation_token)
    except WorkspaceInvitationNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="invitation_not_found",
            message="Приглашение не найдено или уже недействительно.",
            headers={
                "Cache-Control": "no-store",
                "Referrer-Policy": "no-referrer",
            },
        ) from error
    return PublicWorkspaceInvitationApiResponse.model_validate(invitation)


@router.post(
    "/invitations/{invitation_token}/accept",
    response_model=AcceptWorkspaceInvitationApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def accept_workspace_invitation(
    invitation_token: str,
    response: Response,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    service: Annotated[
        WorkspaceInvitationService,
        Depends(get_workspace_invitation_service),
    ],
) -> AcceptWorkspaceInvitationApiResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        await service.accept(
            actor_user_id=context.user.id,
            invitation_token=invitation_token,
            session_token=context.session_id,
        )
    except WorkspaceInvitationNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="invitation_not_found",
            message="Приглашение не найдено или уже недействительно.",
            headers={"Cache-Control": "no-store"},
        ) from error
    except WorkspaceInvitationTransitionError as error:
        raise _invitation_transition_error(error) from error
    return AcceptWorkspaceInvitationApiResponse(
        navigation_outcome=WorkspaceNavigationOutcomeApiResponse(),
    )


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
                has_active_fallback=True,
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


@router.post(
    "/{workspace_id}/deactivate",
    response_model=WorkspaceLifecycleApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def deactivate_workspace(
    workspace_id: UUID,
    request: TransitionWorkspaceLifecycleApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    service: Annotated[
        WorkspaceLifecycleService,
        Depends(get_workspace_lifecycle_service),
    ],
) -> WorkspaceLifecycleApiResponse:
    return await _transition_workspace_lifecycle(
        action="deactivate",
        workspace_id=workspace_id,
        request=request,
        context=context,
        service=service,
    )


@router.post(
    "/{workspace_id}/restore",
    response_model=WorkspaceLifecycleApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def restore_workspace(
    workspace_id: UUID,
    request: TransitionWorkspaceLifecycleApiRequest,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    service: Annotated[
        WorkspaceLifecycleService,
        Depends(get_workspace_lifecycle_service),
    ],
) -> WorkspaceLifecycleApiResponse:
    return await _transition_workspace_lifecycle(
        action="restore",
        workspace_id=workspace_id,
        request=request,
        context=context,
        service=service,
    )


async def _transition_workspace_lifecycle(
    *,
    action: Literal["deactivate", "restore"],
    workspace_id: UUID,
    request: TransitionWorkspaceLifecycleApiRequest,
    context: ApiRequestContext,
    service: WorkspaceLifecycleService,
) -> WorkspaceLifecycleApiResponse:
    command = TransitionWorkspaceLifecycleCommand(
        expected_workspace_updated_at=request.expected_workspace_updated_at,
        expected_current_workspace_id=request.expected_current_workspace_id,
    )
    try:
        result = (
            await service.deactivate(
                actor=context.workspace.user,
                session_token=_session_token(context),
                workspace_id=workspace_id,
                command=command,
            )
            if action == "deactivate"
            else await service.restore(
                actor=context.workspace.user,
                session_token=_session_token(context),
                workspace_id=workspace_id,
                command=command,
            )
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceSessionNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Требуется вход.",
        ) from error
    except WorkspaceSwitchConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="workspace_switch_conflict",
            message=str(error),
            details={"currentWorkspaceId": str(error.current_workspace_id)},
        ) from error
    except WorkspaceLifecycleConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="workspace_lifecycle_conflict",
            message=str(error),
        ) from error
    except WorkspaceLifecycleTransitionError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="workspace_lifecycle_blocked",
            message=str(error),
            details={"reasonCodes": error.reason_codes},
        ) from error
    workspace_context = WorkspaceContext(
        user=result.user,
        workspace=result.workspace,
        membership=result.membership,
    )
    return WorkspaceLifecycleApiResponse(
        session=SessionApiResponseMapper.from_workspace_context(
            workspace_context,
            csrf_token=context.csrf_token,
        ),
        impact=WorkspaceLifecycleMutationImpactApiResponse.model_validate(result.impact),
        navigation_outcome=WorkspaceNavigationOutcomeApiResponse(),
    )


def _session_token(context: ApiRequestContext) -> UUID:
    if context.session_id is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
            message="Требуется вход.",
        )
    return context.session_id


def _workspace_not_found(error: WorkspaceNotFoundError) -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="workspace_not_found",
        message="Пространство не найдено.",
    )


def _member_directory_forbidden(error: WorkspaceMemberDirectoryForbiddenError) -> ApiError:
    return ApiError(
        status_code=status.HTTP_403_FORBIDDEN,
        code="member_directory_forbidden",
        message=str(error),
    )


@router.get(
    "/{workspace_id}/members",
    response_model=WorkspaceMembersApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_workspace_members(
    workspace_id: UUID,
    context: Annotated[ApiRequestContext, Depends(require_api_member_directory_context)],
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
    except WorkspaceMemberDirectoryForbiddenError as error:
        raise _member_directory_forbidden(error) from error
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


@router.get(
    "/{workspace_id}/invitations",
    response_model=WorkspaceInvitationsApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_workspace_invitations(
    workspace_id: UUID,
    response: Response,
    context: Annotated[ApiRequestContext, Depends(require_api_member_directory_context)],
    service: Annotated[
        WorkspaceInvitationService,
        Depends(get_workspace_invitation_service),
    ],
) -> WorkspaceInvitationsApiResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        invitations = await service.read(
            actor_user_id=context.workspace.user.id,
            workspace_id=workspace_id,
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceMemberDirectoryForbiddenError as error:
        raise _member_directory_forbidden(error) from error
    return WorkspaceInvitationsApiResponse.model_validate(invitations)


@router.post(
    "/{workspace_id}/invitations",
    response_model=CreateWorkspaceInvitationApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_workspace_invitation(
    workspace_id: UUID,
    request: CreateWorkspaceInvitationApiRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    response: Response,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    service: Annotated[
        WorkspaceInvitationService,
        Depends(get_workspace_invitation_service),
    ],
    email_sender: Annotated[IdentityEmailSender, Depends(get_identity_email_sender)],
) -> CreateWorkspaceInvitationApiResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        result = await service.create(
            actor_user_id=context.workspace.user.id,
            workspace_id=workspace_id,
            email=request.email,
            role=request.role,
            idempotency_key=idempotency_key,
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceIdempotencyConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="idempotency_conflict",
            message=str(error),
        ) from error
    except InvalidEmailError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"email": [str(error)]},
        ) from error
    except WorkspaceInvitationTransitionError as error:
        raise _invitation_transition_error(error) from error
    share_url = str(
        http_request.url_for(
            "react_spa_path",
            client_path=f"workspaces/invitations/{result.token}",
        )
    )
    background_tasks.add_task(
        email_sender,
        build_workspace_invitation_message(
            recipient=result.invitation.invitee_email,
            workspace_name=context.workspace.workspace.name,
            inviter_name=context.workspace.user.name or context.workspace.user.email,
            role=result.invitation.role.value,
            invitation_url=share_url,
            expires_at=result.invitation.expires_at,
        ),
    )
    return CreateWorkspaceInvitationApiResponse(
        invitation=WorkspaceInvitationItemApiResponse.model_validate(result.invitation),
        invitations=WorkspaceInvitationsApiResponse.model_validate(result.invitations),
        share_url=share_url,
        replayed=result.replayed,
    )


@router.post(
    "/{workspace_id}/invitations/{invitation_id}/revoke",
    response_model=WorkspaceInvitationsApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def revoke_workspace_invitation(
    workspace_id: UUID,
    invitation_id: UUID,
    request: RevokeWorkspaceInvitationApiRequest,
    response: Response,
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    service: Annotated[
        WorkspaceInvitationService,
        Depends(get_workspace_invitation_service),
    ],
) -> WorkspaceInvitationsApiResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        invitations = await service.revoke(
            actor_user_id=context.workspace.user.id,
            workspace_id=workspace_id,
            invitation_id=invitation_id,
            expected_updated_at=request.expected_updated_at,
        )
    except WorkspaceNotFoundError as error:
        raise _workspace_not_found(error) from error
    except WorkspaceInvitationNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="invitation_not_found",
            message="Приглашение не найдено.",
        ) from error
    except WorkspaceInvitationConflictError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="invitation_conflict",
            message=str(error),
        ) from error
    except WorkspaceInvitationTransitionError as error:
        raise _invitation_transition_blocked(error) from error
    return WorkspaceInvitationsApiResponse.model_validate(invitations)


def _invitation_transition_blocked(error: WorkspaceInvitationTransitionError) -> ApiError:
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="invitation_transition_blocked",
        message=str(error),
        details={"reasonCodes": error.reason_codes},
    )


def _invitation_transition_error(error: WorkspaceInvitationTransitionError) -> ApiError:
    reason = error.reason_codes[0] if error.reason_codes else "invitation_transition_blocked"
    if reason == "pending_invitation_exists":
        return ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=reason,
            message=str(error),
            details={"reasonCodes": error.reason_codes},
        )
    if reason == "invitation_email_mismatch":
        return ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=reason,
            message=str(error),
            details={"reasonCodes": error.reason_codes},
        )
    return ApiError(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code=reason,
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
