from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import session_token_from_request
from app.core.settings import Settings
from app.db.session import get_session
from app.features.workspaces.application.invitations import WorkspaceInvitationService
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    get_optional_workspace_context,
)
from app.features.workspaces.errors import WorkspaceInvitationNotFoundError
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(prefix="/workspaces/invitations", tags=["workspace invitations"])
templates = create_templates()


@router.get("/{invitation_token}", response_class=HTMLResponse)
async def preview_workspace_invitation(
    request: Request,
    invitation_token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[
        WorkspaceContext | None,
        Depends(get_optional_workspace_context),
    ] = None,
) -> HTMLResponse:
    try:
        invitation = await WorkspaceInvitationService(session, settings).preview(
            invitation_token=invitation_token
        )
    except WorkspaceInvitationNotFoundError as exc:
        invitation = None
        error = str(exc)
    else:
        error = None

    response = templates.TemplateResponse(
        request,
        "workspaces/accept_invitation.html",
        {
            "app_name": settings.app_name,
            "context": context,
            "current_user": context.user if context else None,
            "invitation": invitation,
            "invitation_token": invitation_token,
            "login_next_path": request.url.path,
            "error": error,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.post("/{invitation_token}/accept")
async def accept_workspace_invitation(
    request: Request,
    invitation_token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    session_token = session_token_from_request(request, settings)
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        await WorkspaceInvitationService(session, settings).accept(
            actor_user_id=context.user.id,
            invitation_token=invitation_token,
            session_token=session_token,
        )
    except WorkspaceInvitationNotFoundError:
        return RedirectResponse(
            url=request.url_for(
                "preview_workspace_invitation",
                invitation_token=invitation_token,
            ).path,
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url="/app/workspaces", status_code=status.HTTP_303_SEE_OTHER)
