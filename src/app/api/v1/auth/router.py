from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    AuthenticatedSessionContext,
    get_authenticated_session_context,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.auth.dependencies import get_authentication_service
from app.api.v1.auth.schemas import (
    AuthConfigApiResponse,
    AuthenticatedApiResponse,
    LoginApiRequest,
    SignupApiRequest,
)
from app.core.config import get_settings
from app.core.security import forget_session, remember_session
from app.core.settings import Settings
from app.features.users.errors import (
    EmailAlreadyRegisteredError,
    InvalidEmailError,
    InvalidPasswordError,
    SignupsClosedError,
    UserError,
)
from app.features.users.service import AuthenticationService, safe_next_path

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigApiResponse)
async def read_auth_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthConfigApiResponse:
    return AuthConfigApiResponse(allow_signups=settings.allow_signups)


@router.post(
    "/signup",
    response_model=AuthenticatedApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def signup(
    request: SignupApiRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    authentication: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> AuthenticatedApiResponse:
    try:
        login_session = await authentication.register(
            email=request.email,
            password=request.password,
            name=request.name,
        )
    except SignupsClosedError as error:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="signups_closed",
            message=str(error),
        ) from error
    except EmailAlreadyRegisteredError as error:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code="email_already_registered",
            message=str(error),
            field_errors={"email": [str(error)]},
        ) from error
    except InvalidEmailError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"email": [str(error)]},
        ) from error
    except InvalidPasswordError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Проверьте переданные данные.",
            field_errors={"password": [str(error)]},
        ) from error

    remember_session(
        response,
        settings=settings,
        session_token=login_session.session_token,
    )
    return AuthenticatedApiResponse(next_path=safe_next_path(request.next_path))


@router.post(
    "/login",
    response_model=AuthenticatedApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def login(
    request: LoginApiRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    authentication: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> AuthenticatedApiResponse:
    try:
        login_session = await authentication.login(
            email=request.email,
            password=request.password,
        )
    except UserError as error:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Неверный email или пароль.",
        ) from error

    remember_session(
        response,
        settings=settings,
        session_token=login_session.session_token,
    )
    return AuthenticatedApiResponse(next_path=safe_next_path(request.next_path))


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def logout(
    response: Response,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    authentication: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> None:
    await authentication.logout(context.session_token)
    forget_session(response, settings=settings)
