from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    csrf_token_for_session,
    session_token_from_request,
    verify_csrf_token,
)
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.service import AuthenticationService
from app.features.workspaces.service import WorkspaceContext

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


async def get_current_workspace_context(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceContext:
    session_token = session_token_from_request(request, settings)
    if session_token is None:
        raise_login_redirect()

    if request.method not in SAFE_METHODS:
        await verify_request_csrf(request, session_token=session_token, settings=settings)

    login_session = await AuthenticationService(session, settings).resolve_login_session(
        session_token
    )
    if login_session is None:
        raise_login_redirect()

    request.state.login_session = login_session
    request.state.csrf_token = csrf_token_for_session(session_token, settings)
    context = WorkspaceContext(user=login_session.user, workspace=login_session.workspace)
    request.state.workspace_context = context
    return context


async def verify_request_csrf(
    request: Request,
    *,
    session_token: str,
    settings: Settings,
) -> None:
    form = await request.form()
    csrf_token = form.get("csrf_token")
    if not isinstance(csrf_token, str) or not verify_csrf_token(
        provided_token=csrf_token,
        session_token=session_token,
        settings=settings,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недействительный CSRF токен.",
        )


def raise_login_redirect() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        detail="Требуется вход.",
        headers={"Location": "/login"},
    )


def parse_uuid_cookie(request: Request, name: str) -> UUID | None:
    raw_value = request.cookies.get(name)
    if not raw_value:
        return None
    try:
        return UUID(raw_value)
    except ValueError:
        return None
