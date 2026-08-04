from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.api.dependencies import (
    AuthenticatedSessionContext,
    get_authenticated_session_context,
    get_password_service,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.account.dependencies import (
    get_account_deactivation_service,
    get_email_change_service,
    get_user_service,
    get_user_session_service,
)
from app.api.v1.account.schemas import (
    AccountApiResponse,
    AccountDeactivationImpactApiResponse,
    ChangePasswordApiRequest,
    ChangePasswordApiResponse,
    ConfirmEmailChangeApiRequest,
    DeactivateAccountApiRequest,
    DeactivateAccountApiResponse,
    DeactivationBlockerApiResponse,
    EmailChangeApiResponse,
    RequestEmailChangeApiRequest,
    RevokeOtherSessionsApiResponse,
    UpdateAccountApiRequest,
    UserSessionApiResponse,
    UserSessionListApiResponse,
)
from app.api.v1.auth.dependencies import get_identity_email_sender
from app.core.config import get_settings
from app.core.security import forget_session, remember_session
from app.core.settings import Settings
from app.features.users.account_deactivation import (
    AccountDeactivationImpact,
    AccountDeactivationService,
    DeactivationBlocker,
)
from app.features.users.email_change import EmailChangeService
from app.features.users.email_delivery import IdentityEmailSender
from app.features.users.errors import (
    AccountDeactivationBlockedError,
    CurrentPasswordIncorrectError,
    CurrentSessionCannotBeRevokedError,
    EmailAlreadyRegisteredError,
    InvalidEmailChangeTokenError,
    InvalidEmailError,
    InvalidPasswordError,
    UserSessionNotFoundError,
)
from app.features.users.passwords import PasswordService
from app.features.users.service import UserService
from app.features.users.sessions import UserSessionService

router = APIRouter(prefix="/account", tags=["account"])


def _deactivation_impact_response(
    impact: AccountDeactivationImpact,
) -> AccountDeactivationImpactApiResponse:
    return AccountDeactivationImpactApiResponse(
        can_deactivate=impact.can_deactivate,
        blockers=[
            DeactivationBlockerApiResponse.model_validate(blocker) for blocker in impact.blockers
        ],
        auto_deactivated_workspace_count=impact.auto_deactivated_workspace_count,
    )


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


@router.post(
    "/email-change-requests",
    response_model=EmailChangeApiResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def request_email_change(
    http_request: Request,
    request: RequestEmailChangeApiRequest,
    background_tasks: BackgroundTasks,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    email_changes: Annotated[EmailChangeService, Depends(get_email_change_service)],
    email_sender: Annotated[IdentityEmailSender, Depends(get_identity_email_sender)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailChangeApiResponse:
    try:
        result = await email_changes.request_change(
            user=context.user,
            current_password=request.current_password,
            target_email=request.target_email,
            base_url=(settings.public_base_url or str(http_request.base_url)).rstrip("/"),
        )
    except CurrentPasswordIncorrectError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"currentPassword": [str(error)]},
        ) from error
    except (InvalidEmailError, EmailAlreadyRegisteredError) as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"targetEmail": [str(error)]},
        ) from error
    for message in result.messages:
        background_tasks.add_task(email_sender, message)
    return EmailChangeApiResponse(
        message="Проверьте новый email и подтвердите изменение по ссылке из письма."
    )


@router.post(
    "/email-changes",
    response_model=EmailChangeApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
    ),
)
async def confirm_email_change(
    request: ConfirmEmailChangeApiRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    email_changes: Annotated[EmailChangeService, Depends(get_email_change_service)],
    email_sender: Annotated[IdentityEmailSender, Depends(get_identity_email_sender)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailChangeApiResponse:
    try:
        result = await email_changes.confirm_change(
            user=context.user,
            session_token=context.session_token,
            token=request.token,
        )
    except InvalidEmailChangeTokenError as error:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_email_change",
            message=str(error),
        ) from error
    except EmailAlreadyRegisteredError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="email_change_conflict",
            message=str(error),
        ) from error
    remember_session(response, settings=settings, session_token=result.session_token)
    background_tasks.add_task(email_sender, result.notification)
    return EmailChangeApiResponse(
        message="Email изменён. Остальные сессии завершены.",
        email=result.email,
    )


@router.get(
    "/deactivation-impact",
    response_model=AccountDeactivationImpactApiResponse,
    responses=api_error_responses(status.HTTP_401_UNAUTHORIZED),
)
async def read_deactivation_impact(
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    deactivation: Annotated[
        AccountDeactivationService,
        Depends(get_account_deactivation_service),
    ],
) -> AccountDeactivationImpactApiResponse:
    return _deactivation_impact_response(await deactivation.impact(user_id=context.user.id))


@router.post(
    "/deactivation",
    response_model=DeactivateAccountApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def deactivate_account(
    request: DeactivateAccountApiRequest,
    response: Response,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    deactivation: Annotated[
        AccountDeactivationService,
        Depends(get_account_deactivation_service),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeactivateAccountApiResponse:
    if request.confirmation != "ДЕАКТИВИРОВАТЬ":
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"confirmation": ["Введите ДЕАКТИВИРОВАТЬ без изменений."]},
        )
    try:
        await deactivation.deactivate(
            user=context.user,
            current_password=request.current_password,
        )
    except CurrentPasswordIncorrectError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"currentPassword": [str(error)]},
        ) from error
    except AccountDeactivationBlockedError as error:
        blockers = [
            DeactivationBlockerApiResponse.model_validate(blocker).model_dump(
                mode="json", by_alias=True
            )
            for blocker in error.blockers
            if isinstance(blocker, DeactivationBlocker)
        ]
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="account_deactivation_blocked",
            message=str(error),
            details={"blockers": blockers},
        ) from error
    forget_session(response, settings=settings)
    return DeactivateAccountApiResponse(
        message="Аккаунт деактивирован. Для восстановления обратитесь к администратору."
    )


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
