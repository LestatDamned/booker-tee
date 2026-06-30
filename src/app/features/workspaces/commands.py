from dataclasses import dataclass
from uuid import UUID

from app.features.workspaces.models import WorkspaceRole, WorkspaceType


@dataclass(frozen=True)
class CreateWorkspaceCommand:
    name: str
    workspace_type: WorkspaceType
    default_currency: str = "RUB"


@dataclass(frozen=True)
class UpdateWorkspaceCommand:
    name: str
    workspace_type: WorkspaceType
    default_currency: str


@dataclass(frozen=True)
class CreateWorkspaceInvitationCommand:
    role: WorkspaceRole


@dataclass(frozen=True)
class UpdateWorkspaceMemberRoleCommand:
    member_id: UUID
    role: WorkspaceRole
