from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.workspaces.service import WorkspaceContext, WorkspaceService


async def get_current_workspace_context(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceContext:
    context = await WorkspaceService(session, settings).resolve_context(
        user_id=parse_uuid_cookie(request, "booker_user_id"),
        workspace_id=parse_uuid_cookie(request, "booker_workspace_id"),
    )
    request.state.workspace_context = context
    return context


def parse_uuid_cookie(request: Request, name: str) -> UUID | None:
    raw_value = request.cookies.get(name)
    if not raw_value:
        return None
    try:
        return UUID(raw_value)
    except ValueError:
        return None
