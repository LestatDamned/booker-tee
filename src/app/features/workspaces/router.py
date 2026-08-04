from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import session_token_from_request
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.errors import UserError
from app.features.users.service import AuthenticationService
from app.features.workspaces.application.invitations import WorkspaceInvitationService
from app.features.workspaces.commands import (
    CreateWorkspaceCommand,
    CreateWorkspaceInvitationCommand,
    UpdateWorkspaceCommand,
    UpdateWorkspaceMemberRoleCommand,
)
from app.features.workspaces.dependencies import (
    get_current_workspace_context,
    get_optional_workspace_context,
    require_member_management_context,
    require_workspace_management_context,
)
from app.features.workspaces.errors import WorkspaceError, WorkspaceInvitationNotFoundError
from app.features.workspaces.models import WorkspaceRole, WorkspaceType
from app.features.workspaces.permissions import (
    INVITABLE_ROLES,
    MANAGEABLE_MEMBER_ROLES,
    can_manage_workspace,
)
from app.features.workspaces.permissions import can_invite_members as can_invite_workspace_members
from app.features.workspaces.presentation.presenter import WorkspacesPagePresenter
from app.features.workspaces.service import WorkspaceContext, WorkspaceService
from app.templating import create_templates

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def workspaces_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    return await render_workspaces_index(
        request=request,
        session=session,
        settings=settings,
        context=context,
    )


@router.post("")
async def create_workspace(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    name: Annotated[str, Form()],
    workspace_type: Annotated[WorkspaceType, Form()] = WorkspaceType.PERSONAL,
    default_currency: Annotated[str, Form()] = "RUB",
) -> Response:
    try:
        workspace = await WorkspaceService(session, settings).create_for_user(
            user_id=context.user.id,
            command=CreateWorkspaceCommand(
                name=name,
                workspace_type=workspace_type,
                default_currency=default_currency,
            ),
        )
    except WorkspaceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    response = RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)
    await switch_session_workspace(
        request=request,
        session=session,
        settings=settings,
        workspace_id=workspace.id,
    )
    return response


@router.post("/{workspace_id}")
async def update_workspace(
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_workspace_management_context)],
    name: Annotated[str, Form()],
    workspace_type: Annotated[WorkspaceType, Form()],
    default_currency: Annotated[str, Form()],
) -> Response:
    try:
        await WorkspaceService(session, settings).update_for_owner(
            owner_id=context.user.id,
            workspace_id=workspace_id,
            command=UpdateWorkspaceCommand(
                name=name,
                workspace_type=workspace_type,
                default_currency=default_currency,
            ),
        )
    except WorkspaceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{workspace_id}/select")
async def select_workspace(
    request: Request,
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
    next_path: Annotated[str | None, Form(alias="next")] = None,
) -> Response:
    workspace = await WorkspaceService(session, settings).get_user_workspace(
        user_id=context.user.id,
        workspace_id=workspace_id,
    )
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await switch_session_workspace(
        request=request,
        session=session,
        settings=settings,
        workspace_id=workspace.id,
    )
    return RedirectResponse(
        url=safe_workspace_return_path(next_path),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{workspace_id}/invitations")
async def create_workspace_invitation(
    request: Request,
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_member_management_context)],
    role: Annotated[WorkspaceRole, Form()] = WorkspaceRole.VIEWER,
) -> Response:
    if workspace_id != context.workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    service = WorkspaceService(session, settings)
    try:
        created_invitation = await service.create_invitation(
            context=context,
            command=CreateWorkspaceInvitationCommand(role=role),
        )
    except WorkspaceError as exc:
        return await render_workspaces_index(
            request=request,
            session=session,
            settings=settings,
            context=context,
            error=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    invitation_link = str(
        request.url_for(
            "preview_workspace_invitation",
            invitation_token=created_invitation.token,
        )
    )
    return await render_workspaces_index(
        request=request,
        session=session,
        settings=settings,
        context=context,
        created_invitation_link=invitation_link,
        created_invitation_expires_at=created_invitation.invitation.expires_at,
        status_code=status.HTTP_201_CREATED,
    )


@router.post("/{workspace_id}/invitations/{invitation_id}/revoke")
async def revoke_workspace_invitation(
    workspace_id: UUID,
    invitation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_member_management_context)],
) -> Response:
    if workspace_id != context.workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await WorkspaceService(session, settings).revoke_invitation(
            context=context,
            invitation_id=invitation_id,
        )
    except WorkspaceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{workspace_id}/members/{member_id}/role")
async def update_workspace_member_role(
    workspace_id: UUID,
    member_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_member_management_context)],
    role: Annotated[WorkspaceRole, Form()],
) -> Response:
    if workspace_id != context.workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await WorkspaceService(session, settings).update_member_role(
            context=context,
            command=UpdateWorkspaceMemberRoleCommand(member_id=member_id, role=role),
        )
    except WorkspaceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{workspace_id}/members/{member_id}/disable")
async def disable_workspace_member(
    workspace_id: UUID,
    member_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_member_management_context)],
) -> Response:
    if workspace_id != context.workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await WorkspaceService(session, settings).disable_member(
            context=context,
            member_id=member_id,
        )
    except WorkspaceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{workspace_id}/members/{member_id}/reactivate")
async def reactivate_workspace_member(
    workspace_id: UUID,
    member_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(require_member_management_context)],
) -> Response:
    if workspace_id != context.workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        await WorkspaceService(session, settings).reactivate_member(
            context=context,
            member_id=member_id,
        )
    except WorkspaceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/invitations/{invitation_token}", response_class=HTMLResponse)
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


@router.post("/invitations/{invitation_token}/accept")
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


async def render_workspaces_index(
    *,
    request: Request,
    session: AsyncSession,
    settings: Settings,
    context: WorkspaceContext,
    created_invitation_link: str | None = None,
    created_invitation_expires_at: object | None = None,
    error: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    service = WorkspaceService(session, settings)
    workspace_return_path = current_request_path(request)
    user_workspaces = await service.list_user_workspaces(context.user.id)
    members = await service.list_workspace_members(context)
    pending_invitations = await service.list_pending_invitations(context)
    audit_events = await service.list_recent_audit_events(context)
    return templates.TemplateResponse(
        request,
        "workspaces/index.html",
        {
            "app_name": settings.app_name,
            "current_user": context.user,
            "workspace": context.workspace,
            "workspace_page": WorkspacesPagePresenter.build_index(
                user_workspaces,
                members=members,
                pending_invitations=pending_invitations,
                audit_events=audit_events,
                current_workspace_id=context.workspace.id,
                current_default_currency=context.workspace.default_currency,
                current_user_id=context.user.id,
                actor_membership=context.membership,
                can_manage_workspace=can_manage_workspace(context.membership),
                select_return_path=workspace_return_path,
                member_roles=MANAGEABLE_MEMBER_ROLES,
            ),
            "workspace_types": list(WorkspaceType),
            "workspaces": user_workspaces,
            "members": members,
            "member_roles": MANAGEABLE_MEMBER_ROLES,
            "pending_invitations": pending_invitations,
            "audit_events": audit_events,
            "invite_roles": INVITABLE_ROLES,
            "can_invite_members": can_invite_workspace_members(context.membership),
            "created_invitation_link": created_invitation_link,
            "created_invitation_expires_at": created_invitation_expires_at,
            "workspace_return_path": workspace_return_path,
            "error": error,
        },
        status_code=status_code,
    )


async def switch_session_workspace(
    *,
    request: Request,
    session: AsyncSession,
    settings: Settings,
    workspace_id: UUID,
) -> None:
    session_token = session_token_from_request(request, settings)
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    try:
        await AuthenticationService(session, settings).switch_workspace(
            session_token=session_token,
            workspace_id=workspace_id,
        )
    except UserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def current_request_path(request: Request) -> str:
    path = request.url.path
    if request.url.query:
        return f"{path}?{request.url.query}"
    return path


def safe_workspace_return_path(next_path: str | None) -> str:
    if not next_path:
        return "/workspaces"
    if not next_path.startswith("/") or next_path.startswith("//"):
        return "/workspaces"
    return next_path
