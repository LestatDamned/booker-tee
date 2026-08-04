from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.workspaces.application.creation import WorkspaceCreator
from app.features.workspaces.application.directory import WorkspaceDirectoryReader
from app.features.workspaces.application.invitations import WorkspaceInvitationService
from app.features.workspaces.application.lifecycle import WorkspaceLifecycleService
from app.features.workspaces.application.members import WorkspaceMemberService
from app.features.workspaces.application.ownership import WorkspaceOwnershipService
from app.features.workspaces.application.settings import WorkspaceSettingsService
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


def get_workspace_settings_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceSettingsService:
    return WorkspaceSettingsService(session)


def get_workspace_member_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceMemberService:
    return WorkspaceMemberService(session)


def get_workspace_invitation_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceInvitationService:
    return WorkspaceInvitationService(session, settings)


def get_workspace_lifecycle_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceLifecycleService:
    return WorkspaceLifecycleService(session)


def get_workspace_ownership_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceOwnershipService:
    return WorkspaceOwnershipService(session)
