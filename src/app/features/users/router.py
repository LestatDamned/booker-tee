from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.errors import UserError
from app.features.users.service import UserService
from app.features.workspaces.service import WorkspaceService
from app.templating import create_templates

router = APIRouter(prefix="/users", tags=["users"])
templates = create_templates()


@router.get("", response_class=HTMLResponse)
async def users_index(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    users = await UserService(session).list_active()
    return templates.TemplateResponse(
        request,
        "users/index.html",
        {
            "app_name": settings.app_name,
            "current_user_id": request.cookies.get("booker_user_id"),
            "users": users,
        },
    )


@router.post("")
async def create_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    email: Annotated[str, Form()],
    name: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        user, workspace = await UserService(session).create_with_personal_workspace(
            email=email,
            name=name,
        )
    except UserError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    response = RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)
    remember_context(response, user_id=user.id, workspace_id=workspace.id)
    return response


@router.post("/{user_id}/select")
async def select_user(
    request: Request,
    user_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    user = await UserService(session).get_active(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    context = await WorkspaceService(session, settings).resolve_context(user_id=user.id)
    response = RedirectResponse(
        url=request.headers.get("referer") or "/workspaces",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    remember_context(response, user_id=user.id, workspace_id=context.workspace.id)
    return response


def remember_context(response: Response, *, user_id: UUID, workspace_id: UUID) -> None:
    response.set_cookie("booker_user_id", str(user_id), httponly=True, samesite="lax")
    response.set_cookie("booker_workspace_id", str(workspace_id), httponly=True, samesite="lax")
