from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.workspaces.service import WorkspaceContext, WorkspaceService


async def get_current_workspace_context(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceContext:
    return await WorkspaceService(session, settings).ensure_development_context()
