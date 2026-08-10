from uuid import UUID

from app.api.schemas import ApiModel
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)


class SessionUserApiResponse(ApiModel):
    id: UUID
    email: str
    name: str | None


class SessionWorkspaceApiResponse(ApiModel):
    id: UUID
    name: str
    type: WorkspaceType
    default_currency: str


class SessionMembershipApiResponse(ApiModel):
    role: WorkspaceRole
    status: WorkspaceMemberStatus


class SessionCapabilitiesApiResponse(ApiModel):
    can_read_workspace: bool
    can_write_financial_data: bool
    can_manage_imports: bool
    can_view_raw_import_data: bool
    can_view_member_directory: bool
    can_manage_members: bool
    can_view_workspace_activity: bool
    can_manage_workspace: bool


class SessionApiResponse(ApiModel):
    user: SessionUserApiResponse
    workspace: SessionWorkspaceApiResponse
    membership: SessionMembershipApiResponse
    capabilities: SessionCapabilitiesApiResponse
    csrf_token: str
