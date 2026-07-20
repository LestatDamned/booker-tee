from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.features.workspaces.models import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


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
