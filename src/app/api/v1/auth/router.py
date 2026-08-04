from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.api.dependencies import (
    AuthenticatedSessionContext,
    get_authenticated_session_context,
    require_same_origin_public_mutation,
)
from app.api.errors import ApiError, api_error_responses
from app.api.v1.auth.dependencies import (
    get_authentication_service,
    get_email_verification_service,
    get_identity_email_sender,
)
from app.api.v1.auth.schemas import (
    AuthConfigApiResponse,
    AuthenticatedApiResponse,
    EmailVerificationApiRequest,
    EmailVerificationRequestApiRequest,
    LoginApiRequest,
    SignupApiRequest,
    VerificationRequestedApiResponse,
)
from app.core.config import get_settings
from app.core.security import forget_session, remember_session
from app.core.settings import Settings
from app.features.users.email_delivery import IdentityEmailSender
from app.features.users.email_verification import EmailVerificationService
from app.features.users.errors import (
    AuthRateLimitedError,
    InvalidEmailError,
    InvalidEmailVerificationTokenError,
    InvalidPasswordError,
    SignupsClosedError,
    UserError,
)
from app.features.users.service import AuthenticationService, safe_next_path

router = APIRouter(prefix="/auth", tags=["auth"])
_VERIFICATION_REQUESTED_MESSAGE = (
    "Если адрес подходит для регистрации, мы отправили письмо с подтверждением."
)


def _public_base_url(request: Request, settings: Settings) -> str:
    return (settings.public_base_url or str(request.base_url)).rstrip("/")


@router.get("/config", response_model=AuthConfigApiResponse)
async def read_auth_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthConfigApiResponse:
    return AuthConfigApiResponse(
        allow_signups=settings.allow_signups,
        password_min_length=settings.password_min_length,
    )


@router.post(
    "/signup",
    response_model=VerificationRequestedApiResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_same_origin_public_mutation)],
    responses=api_error_responses(
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def signup(
    http_request: Request,
    request: SignupApiRequest,
    background_tasks: BackgroundTasks,
    verification: Annotated[
        EmailVerificationService,
        Depends(get_email_verification_service),
    ],
    email_sender: Annotated[IdentityEmailSender, Depends(get_identity_email_sender)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VerificationRequestedApiResponse:
    try:
        result = await verification.request_signup(
            email=request.email,
            password=request.password,
            name=request.name,
            base_url=_public_base_url(http_request, settings),
            next_path=request.next_path,
        )
    except SignupsClosedError as error:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="signups_closed",
            message=str(error),
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

    if result.email is not None:
        background_tasks.add_task(email_sender, result.email)
    return VerificationRequestedApiResponse(
        message=_VERIFICATION_REQUESTED_MESSAGE,
        retry_after_seconds=result.retry_after_seconds,
    )


@router.post(
    "/email-verification-requests",
    response_model=VerificationRequestedApiResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_same_origin_public_mutation)],
    responses=api_error_responses(
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        status.HTTP_429_TOO_MANY_REQUESTS,
    ),
)
async def request_email_verification(
    http_request: Request,
    request: EmailVerificationRequestApiRequest,
    background_tasks: BackgroundTasks,
    verification: Annotated[
        EmailVerificationService,
        Depends(get_email_verification_service),
    ],
    email_sender: Annotated[IdentityEmailSender, Depends(get_identity_email_sender)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VerificationRequestedApiResponse:
    try:
        result = await verification.request_resend(
            email=request.email,
            base_url=_public_base_url(http_request, settings),
            network_key=http_request.client.host if http_request.client else "unknown",
        )
    except InvalidEmailError:
        return VerificationRequestedApiResponse(
            message=_VERIFICATION_REQUESTED_MESSAGE,
            retry_after_seconds=60,
        )
    except AuthRateLimitedError as error:
        raise ApiError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="auth_rate_limited",
            message=str(error),
            details={"retryAfterSeconds": error.retry_after_seconds},
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error

    if result.email is not None:
        background_tasks.add_task(email_sender, result.email)
    return VerificationRequestedApiResponse(
        message=_VERIFICATION_REQUESTED_MESSAGE,
        retry_after_seconds=result.retry_after_seconds,
    )


@router.post(
    "/email-verifications",
    response_model=AuthenticatedApiResponse,
    dependencies=[Depends(require_same_origin_public_mutation)],
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def verify_email(
    request: EmailVerificationApiRequest,
    response: Response,
    verification: Annotated[
        EmailVerificationService,
        Depends(get_email_verification_service),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedApiResponse:
    try:
        login_session = await verification.verify(token=request.token)
    except InvalidEmailVerificationTokenError as error:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_email_verification",
            message=str(error),
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
    dependencies=[Depends(require_same_origin_public_mutation)],
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
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
