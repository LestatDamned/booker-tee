from dataclasses import dataclass
from datetime import datetime
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
class UpdateWorkspaceSettingsCommand:
    name: str
    workspace_type: WorkspaceType
    default_currency: str
    expected_updated_at: datetime


@dataclass(frozen=True)
class CreateWorkspaceInvitationCommand:
    role: WorkspaceRole


@dataclass(frozen=True)
class UpdateWorkspaceMemberRoleCommand:
    member_id: UUID
    role: WorkspaceRole


@dataclass(frozen=True)
class UpdateWorkspaceMemberRoleApiCommand:
    member_id: UUID
    role: WorkspaceRole
    expected_updated_at: datetime


@dataclass(frozen=True)
class TransitionWorkspaceMemberCommand:
    member_id: UUID
    expected_updated_at: datetime


@dataclass(frozen=True)
class TransferWorkspaceOwnershipCommand:
    recipient_member_id: UUID
    expected_workspace_updated_at: datetime
    expected_recipient_updated_at: datetime


@dataclass(frozen=True)
class LeaveWorkspaceCommand:
    expected_member_updated_at: datetime
    expected_current_workspace_id: UUID
