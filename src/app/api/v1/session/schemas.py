from uuid import UUID

from app.api.schemas import ApiModel
from app.features.workspaces.models import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)


class SessionUser(ApiModel):
    id: UUID
    email: str
    name: str | None


class SessionWorkspace(ApiModel):
    id: UUID
    name: str
    type: WorkspaceType
    default_currency: str


class SessionMembership(ApiModel):
    role: WorkspaceRole
    status: WorkspaceMemberStatus


class SessionCapabilities(ApiModel):
    can_read_workspace: bool
    can_write_financial_data: bool
    can_manage_imports: bool
    can_manage_members: bool
    can_manage_workspace: bool


class SessionResponse(ApiModel):
    user: SessionUser
    workspace: SessionWorkspace
    membership: SessionMembership
    capabilities: SessionCapabilities
    csrf_token: str
