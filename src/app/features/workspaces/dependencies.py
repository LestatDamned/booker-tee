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
from app.features.workspaces.permissions import (
    can_manage_imports,
    can_manage_members,
    can_manage_workspace,
    can_read_workspace,
    can_write_financial_data,
)
from app.features.workspaces.repository import WorkspaceRepository
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

    if request.method not in SAFE_METHODS:
        workspace = await WorkspaceRepository(session).lock_for_update(login_session.workspace.id)
        if workspace is None or not workspace.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пространство было деактивировано. Обновите страницу.",
            )

    request.state.login_session = login_session
    request.state.csrf_token = csrf_token_for_session(session_token, settings)
    context = WorkspaceContext(
        user=login_session.user,
        workspace=login_session.workspace,
        membership=login_session.membership,
    )
    request.state.workspace_context = context
    return context


async def require_workspace_read_context(
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> WorkspaceContext:
    return require_workspace_permission(
        context,
        allowed=can_read_workspace(context.membership),
        message="Недостаточно прав для просмотра workspace.",
    )


async def require_financial_write_context(
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> WorkspaceContext:
    return require_workspace_permission(
        context,
        allowed=can_write_financial_data(context.membership),
        message="Недостаточно прав для изменения финансовых данных.",
    )


async def require_import_management_context(
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> WorkspaceContext:
    return require_workspace_permission(
        context,
        allowed=can_manage_imports(context.membership),
        message="Недостаточно прав для управления импортом.",
    )


async def require_member_management_context(
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> WorkspaceContext:
    return require_workspace_permission(
        context,
        allowed=can_manage_members(context.membership),
        message="Недостаточно прав для управления участниками.",
    )


async def require_workspace_management_context(
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> WorkspaceContext:
    return require_workspace_permission(
        context,
        allowed=can_manage_workspace(context.membership),
        message="Недостаточно прав для управления workspace.",
    )


async def get_optional_workspace_context(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceContext | None:
    session_token = session_token_from_request(request, settings)
    if session_token is None:
        return None

    login_session = await AuthenticationService(session, settings).resolve_login_session(
        session_token
    )
    if login_session is None:
        return None

    request.state.login_session = login_session
    request.state.csrf_token = csrf_token_for_session(session_token, settings)
    context = WorkspaceContext(
        user=login_session.user,
        workspace=login_session.workspace,
        membership=login_session.membership,
    )
    request.state.workspace_context = context
    return context


def require_workspace_permission(
    context: WorkspaceContext,
    *,
    allowed: bool,
    message: str,
) -> WorkspaceContext:
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)
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
        session_id=session_token,
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
        headers={"Location": "/app/auth/login"},
    )


def parse_uuid_cookie(request: Request, name: str) -> UUID | None:
    raw_value = request.cookies.get(name)
    if not raw_value:
        return None
    try:
        return UUID(raw_value)
    except ValueError:
        return None
