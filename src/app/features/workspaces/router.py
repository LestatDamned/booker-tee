from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.service import UserService
from app.features.workspaces.commands import CreateWorkspaceCommand, UpdateWorkspaceCommand
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.errors import WorkspaceError
from app.features.workspaces.models import WorkspaceType
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
    service = WorkspaceService(session, settings)
    users = await UserService(session).list_active()
    workspaces = await service.list_user_workspaces(context.user.id)
    return templates.TemplateResponse(
        request,
        "workspaces/index.html",
        {
            "app_name": settings.app_name,
            "current_user": context.user,
            "users": users,
            "workspace": context.workspace,
            "workspace_types": list(WorkspaceType),
            "workspaces": workspaces,
        },
    )


@router.post("")
async def create_workspace(
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
    remember_workspace(response, workspace.id)
    return response


@router.post("/{workspace_id}")
async def update_workspace(
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
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
    workspace_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    workspace = await WorkspaceService(session, settings).get_user_workspace(
        user_id=context.user.id,
        workspace_id=workspace_id,
    )
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    response = RedirectResponse(url="/accounts", status_code=status.HTTP_303_SEE_OTHER)
    remember_workspace(response, workspace.id)
    return response


def remember_workspace(response: Response, workspace_id: UUID) -> None:
    response.set_cookie("booker_workspace_id", str(workspace_id), httponly=True, samesite="lax")
