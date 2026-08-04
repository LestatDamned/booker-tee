from dataclasses import dataclass
from typing import Annotated, NoReturn
from urllib.parse import urlsplit

from fastapi import Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ApiError
from app.core.config import get_settings
from app.core.security import (
    csrf_token_for_session,
    session_token_from_request,
    verify_csrf_token,
)
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.models import User, UserSession
from app.features.users.service import AuthenticationService
from app.features.workspaces.permissions import can_read_workspace, can_write_financial_data
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.service import WorkspaceContext

API_CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


@dataclass(frozen=True)
class ApiRequestContext:
    workspace: WorkspaceContext
    csrf_token: str
    session_token: str | None = None


@dataclass(frozen=True)
class AuthenticatedSessionContext:
    user: User
    session: UserSession
    csrf_token: str
    session_token: str


def require_same_origin_public_mutation(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    fetch_site = request.headers.get("Sec-Fetch-Site", "").lower()
    if fetch_site == "cross-site":
        raise_invalid_origin()
    if fetch_site == "same-origin":
        return

    provided_origin = request.headers.get("Origin")
    expected_origin = _origin(settings.public_base_url or str(request.base_url))
    if provided_origin is None or _origin(provided_origin) != expected_origin:
        raise_invalid_origin()


async def get_authenticated_session_context(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedSessionContext:
    session_token = session_token_from_request(request, settings)
    if session_token is None:
        raise_api_unauthorized()
    if request.method not in SAFE_METHODS:
        verify_api_csrf(request, session_token=session_token, settings=settings)

    authenticated = await AuthenticationService(
        session,
        settings,
    ).resolve_authenticated_session(session_token)
    if authenticated is None:
        raise_api_unauthorized()
    return AuthenticatedSessionContext(
        user=authenticated.user,
        session=authenticated.session,
        csrf_token=csrf_token_for_session(session_token, settings),
        session_token=session_token,
    )


async def get_api_request_context(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApiRequestContext:
    session_token = session_token_from_request(request, settings)
    if session_token is None:
        raise_api_unauthorized()

    if request.method not in SAFE_METHODS:
        verify_api_csrf(request, session_token=session_token, settings=settings)

    login_session = await AuthenticationService(session, settings).resolve_login_session(
        session_token
    )
    if login_session is None:
        raise_api_unauthorized()

    if request.method not in SAFE_METHODS:
        workspace = await WorkspaceRepository(session).lock_for_update(login_session.workspace.id)
        if workspace is None or not workspace.is_active:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code="workspace_inactive",
                message="Пространство было деактивировано. Обновите страницу.",
            )

    workspace_context = WorkspaceContext(
        user=login_session.user,
        workspace=login_session.workspace,
        membership=login_session.membership,
    )
    if not can_read_workspace(workspace_context.membership):
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="workspace_forbidden",
            message="Недостаточно прав для просмотра workspace.",
        )

    csrf_token = csrf_token_for_session(session_token, settings)
    return ApiRequestContext(
        workspace=workspace_context,
        csrf_token=csrf_token,
        session_token=session_token,
    )


def require_api_financial_write_context(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
) -> ApiRequestContext:
    if not can_write_financial_data(context.workspace.membership):
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="financial_write_forbidden",
            message="Недостаточно прав для изменения финансовых данных.",
        )
    return context


def verify_api_csrf(
    request: Request,
    *,
    session_token: str,
    settings: Settings,
) -> None:
    provided_token = request.headers.get(API_CSRF_HEADER)
    if not verify_csrf_token(
        provided_token=provided_token,
        session_token=session_token,
        settings=settings,
    ):
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="invalid_csrf",
            message="Недействительный CSRF токен.",
        )


def raise_api_unauthorized() -> NoReturn:
    raise ApiError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="unauthorized",
        message="Требуется вход.",
    )


def raise_invalid_origin() -> NoReturn:
    raise ApiError(
        status_code=status.HTTP_403_FORBIDDEN,
        code="invalid_origin",
        message="Источник запроса не разрешён.",
    )


def _origin(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
