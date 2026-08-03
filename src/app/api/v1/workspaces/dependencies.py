from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.workspaces.application.creation import WorkspaceCreator
from app.features.workspaces.application.directory import WorkspaceDirectoryReader
from app.features.workspaces.application.switching import WorkspaceSessionSwitcher
from app.features.workspaces.repository import WorkspaceRepository


def get_workspace_directory_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceDirectoryReader:
    return WorkspaceDirectoryReader(WorkspaceRepository(session))


def get_workspace_creator(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceCreator:
    return WorkspaceCreator(session)


def get_workspace_session_switcher(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceSessionSwitcher:
    return WorkspaceSessionSwitcher(session)
