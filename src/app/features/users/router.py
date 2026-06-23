from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import forget_session, remember_session, session_token_from_request
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.errors import UserError
from app.features.users.service import AuthenticationService
from app.features.workspaces.dependencies import get_current_workspace_context
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

router = APIRouter(tags=["users"])
templates = create_templates()


@router.get("/signup", response_class=HTMLResponse)
async def signup_form(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "users/signup.html",
        {
            "allow_signups": settings.allow_signups,
            "app_name": settings.app_name,
            "error": None,
        },
    )


@router.post("/signup")
async def signup(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    name: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        login_session = await AuthenticationService(session, settings).register(
            email=email,
            password=password,
            name=name,
        )
    except UserError as exc:
        return templates.TemplateResponse(
            request,
            "users/signup.html",
            {
                "allow_signups": settings.allow_signups,
                "app_name": settings.app_name,
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    response = RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)
    remember_session(response, settings=settings, session_token=login_session.session_token)
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_form(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "users/login.html",
        {
            "app_name": settings.app_name,
            "error": None,
        },
    )


@router.post("/login")
async def login(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    try:
        login_session = await AuthenticationService(session, settings).login(
            email=email,
            password=password,
        )
    except UserError as exc:
        return templates.TemplateResponse(
            request,
            "users/login.html",
            {
                "app_name": settings.app_name,
                "error": str(exc),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    response = RedirectResponse(url="/workspaces", status_code=status.HTTP_303_SEE_OTHER)
    remember_session(response, settings=settings, session_token=login_session.session_token)
    return response


@router.get("/users", response_class=HTMLResponse)
async def user_profile(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "users/index.html",
        {
            "app_name": settings.app_name,
            "current_user": context.user,
            "workspace": context.workspace,
        },
    )


@router.post("/logout")
async def logout(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    _context: Annotated[WorkspaceContext, Depends(get_current_workspace_context)],
) -> Response:
    session_token = session_token_from_request(request, settings)
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    await AuthenticationService(session, settings).logout(session_token)
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    forget_session(response, settings=settings)
    return response
