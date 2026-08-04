from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    AuthenticatedSessionContext,
    get_authenticated_session_context,
    get_password_service,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.account.dependencies import get_user_service
from app.api.v1.account.schemas import (
    AccountApiResponse,
    ChangePasswordApiRequest,
    ChangePasswordApiResponse,
    UpdateAccountApiRequest,
)
from app.core.config import get_settings
from app.core.security import remember_session
from app.core.settings import Settings
from app.features.users.errors import CurrentPasswordIncorrectError, InvalidPasswordError
from app.features.users.passwords import PasswordService
from app.features.users.service import UserService

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
