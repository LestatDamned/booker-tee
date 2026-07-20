from dataclasses import dataclass
from typing import Annotated, NoReturn

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
from app.features.users.service import AuthenticationService
from app.features.workspaces.permissions import can_read_workspace, can_write_financial_data
from app.features.workspaces.service import WorkspaceContext

API_CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


@dataclass(frozen=True)
class ApiRequestContext:
    workspace: WorkspaceContext
    csrf_token: str


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
    request.state.login_session = login_session
    request.state.csrf_token = csrf_token
    request.state.workspace_context = workspace_context
    return ApiRequestContext(workspace=workspace_context, csrf_token=csrf_token)


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
