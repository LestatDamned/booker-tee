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
    workspaces = await service.list_user_workspaces(context.user.id)
    return templates.TemplateResponse(
        request,
        "workspaces/index.html",
        {
            "app_name": settings.app_name,
            "current_user": context.user,
            "workspace": context.workspace,
            "workspace_types": list(WorkspaceType),
            "workspaces": workspaces,
        },
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
    request: Request,
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

    await switch_session_workspace(
        request=request,
        session=session,
        settings=settings,
        workspace_id=workspace.id,
    )
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)


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
