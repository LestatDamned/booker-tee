from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    AuthenticatedSessionContext,
    get_authenticated_session_context,
    get_password_service,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.account.dependencies import get_user_service, get_user_session_service
from app.api.v1.account.schemas import (
    AccountApiResponse,
    ChangePasswordApiRequest,
    ChangePasswordApiResponse,
    RevokeOtherSessionsApiResponse,
    UpdateAccountApiRequest,
    UserSessionApiResponse,
    UserSessionListApiResponse,
)
from app.core.config import get_settings
from app.core.security import remember_session
from app.core.settings import Settings
from app.features.users.errors import (
    CurrentPasswordIncorrectError,
    CurrentSessionCannotBeRevokedError,
    InvalidPasswordError,
    UserSessionNotFoundError,
)
from app.features.users.passwords import PasswordService
from app.features.users.service import UserService
from app.features.users.sessions import UserSessionService

router = APIRouter(prefix="/account", tags=["account"])


@router.get(
    "",
    response_model=AccountApiResponse,
    responses=api_error_responses(status.HTTP_401_UNAUTHORIZED),
)
async def read_account(
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
) -> AccountApiResponse:
    return AccountApiResponse.model_validate(context.user)


@router.patch(
    "",
    response_model=AccountApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_account(
    request: UpdateAccountApiRequest,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    users: Annotated[UserService, Depends(get_user_service)],
) -> AccountApiResponse:
    user = await users.update_name(user=context.user, name=request.name)
    return AccountApiResponse.model_validate(user)


@router.patch(
    "/password",
    response_model=ChangePasswordApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def change_password(
    request: ChangePasswordApiRequest,
    response: Response,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    passwords: Annotated[PasswordService, Depends(get_password_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChangePasswordApiResponse:
    try:
        session_token = await passwords.change_password(
            user=context.user,
            session_token=context.session_token,
            current_password=request.current_password,
            new_password=request.new_password,
        )
    except CurrentPasswordIncorrectError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"currentPassword": [str(error)]},
        ) from error
    except InvalidPasswordError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"newPassword": [str(error)]},
        ) from error

    remember_session(response, settings=settings, session_token=session_token)
    return ChangePasswordApiResponse(message="Пароль изменён. Остальные сессии завершены.")


@router.get(
    "/sessions",
    response_model=UserSessionListApiResponse,
    responses=api_error_responses(status.HTTP_401_UNAUTHORIZED),
)
async def list_sessions(
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    sessions: Annotated[UserSessionService, Depends(get_user_session_service)],
) -> UserSessionListApiResponse:
    items = await sessions.list_active(
        user_id=context.user.id,
        current_session_id=context.session.id,
    )
    return UserSessionListApiResponse(
        items=[UserSessionApiResponse.model_validate(item) for item in items]
    )


@router.delete(
    "/sessions/others",
    response_model=RevokeOtherSessionsApiResponse,
    responses=api_error_responses(status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
)
async def revoke_other_sessions(
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    sessions: Annotated[UserSessionService, Depends(get_user_session_service)],
) -> RevokeOtherSessionsApiResponse:
    revoked_count = await sessions.revoke_others(
        user_id=context.user.id,
        current_session_id=context.session.id,
    )
    return RevokeOtherSessionsApiResponse(revoked_count=revoked_count)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def revoke_session(
    session_id: UUID,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    sessions: Annotated[UserSessionService, Depends(get_user_session_service)],
) -> Response:
    try:
        await sessions.revoke(
            user_id=context.user.id,
            current_session_id=context.session.id,
            session_id=session_id,
        )
    except CurrentSessionCannotBeRevokedError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="current_session_requires_logout",
            message=str(error),
        ) from error
    except UserSessionNotFoundError as error:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="session_not_found",
            message=str(error),
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
