from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from app.api.schemas import ApiModel, ApiRequestModel
from app.api.v1.session.responses import SessionApiResponse
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.schemas import (
    WorkspaceBlockingReason,
    WorkspaceMemberBlockingReason,
)


class WorkspaceMembershipApiResponse(ApiModel):
    role: WorkspaceRole
    status: WorkspaceMemberStatus
    updated_at: datetime


class WorkspaceItemCapabilitiesApiResponse(ApiModel):
    can_select: bool
    can_update: bool
    can_manage_members: bool
    can_invite: bool
    can_leave: bool
    can_deactivate: bool
    can_restore: bool


class WorkspaceDirectoryItemApiResponse(ApiModel):
    id: UUID
    name: str
    type: WorkspaceType
    default_currency: str
    is_active: bool
    archived_at: datetime | None
    updated_at: datetime
    membership: WorkspaceMembershipApiResponse
    is_current: bool
    capabilities: WorkspaceItemCapabilitiesApiResponse
    blocking_reason_codes: list[WorkspaceBlockingReason]


class WorkspaceDirectoryCapabilitiesApiResponse(ApiModel):
    can_create: bool


class WorkspaceOptionApiResponse(ApiModel):
    value: str
    label: str


class WorkspaceDirectoryApiResponse(ApiModel):
    current_workspace_id: UUID
    items: list[WorkspaceDirectoryItemApiResponse]
    capabilities: WorkspaceDirectoryCapabilitiesApiResponse
    workspace_type_options: list[WorkspaceOptionApiResponse]
    currency_options: list[WorkspaceOptionApiResponse]


class WorkspaceSettingsCapabilitiesApiResponse(ApiModel):
    can_update: bool
    can_manage_members: bool
    can_invite: bool
    can_deactivate: bool
    can_restore: bool


class WorkspaceLifecycleImpactApiResponse(ApiModel):
    financial_history_preserved: bool
    current_session_count: int
    pending_invitation_count: int
    active_integration_connection_count: int
    active_chat_identity_binding_count: int


class WorkspaceSettingsItemApiResponse(ApiModel):
    id: UUID
    name: str
    type: WorkspaceType
    default_currency: str
    is_active: bool
    archived_at: datetime | None
    updated_at: datetime
    membership: WorkspaceMembershipApiResponse
    capabilities: WorkspaceSettingsCapabilitiesApiResponse
    blocking_reason_codes: list[WorkspaceBlockingReason]


class WorkspaceSettingsApiResponse(ApiModel):
    workspace: WorkspaceSettingsItemApiResponse
    workspace_type_options: list[WorkspaceOptionApiResponse]
    currency_options: list[WorkspaceOptionApiResponse]
    lifecycle_impact: WorkspaceLifecycleImpactApiResponse | None


class CreateWorkspaceApiRequest(ApiRequestModel):
    name: str = Field(max_length=255)
    workspace_type: WorkspaceType
    default_currency: str = Field(default="RUB", min_length=3, max_length=3)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if isinstance(value, str):
            return " ".join(value.split())
        return value

    @field_validator("name")
    @classmethod
    def require_name(cls, name: str) -> str:
        if not name:
            raise PydanticCustomError(
                "workspace_name_required",
                "Название пространства обязательно.",
            )
        return name

    @field_validator("default_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class SelectWorkspaceApiRequest(ApiRequestModel):
    expected_current_workspace_id: UUID


class UpdateWorkspaceSettingsApiRequest(ApiRequestModel):
    name: str = Field(max_length=255)
    workspace_type: WorkspaceType
    default_currency: str = Field(min_length=3, max_length=3)
    expected_updated_at: datetime

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if isinstance(value, str):
            return " ".join(value.split())
        return value

    @field_validator("name")
    @classmethod
    def require_name(cls, name: str) -> str:
        if not name:
            raise PydanticCustomError(
                "workspace_name_required",
                "Название пространства обязательно.",
            )
        return name

    @field_validator("default_currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value


class WorkspaceNavigationOutcomeApiResponse(ApiModel):
    kind: Literal["workspace_changed"] = "workspace_changed"
    href: Literal["/app/workspaces"] = "/app/workspaces"
    boundary: Literal["hard_reload"] = "hard_reload"


class CreateWorkspaceApiResponse(ApiModel):
    workspace: WorkspaceDirectoryItemApiResponse
    session: SessionApiResponse
    navigation_outcome: WorkspaceNavigationOutcomeApiResponse
    replayed: bool


class SelectWorkspaceApiResponse(ApiModel):
    session: SessionApiResponse
    navigation_outcome: WorkspaceNavigationOutcomeApiResponse


class WorkspaceMemberCapabilitiesApiResponse(ApiModel):
    can_update_role: bool
    can_disable: bool
    can_reactivate: bool
    can_transfer_ownership: bool
    can_leave: bool
    assignable_roles: list[WorkspaceRole]


class WorkspaceMemberItemApiResponse(ApiModel):
    id: UUID
    user_id: UUID
    name: str | None
    email: str
    role: WorkspaceRole
    status: WorkspaceMemberStatus
    joined_at: datetime | None
    updated_at: datetime
    is_self: bool
    capabilities: WorkspaceMemberCapabilitiesApiResponse
    blocking_reason_codes: list[WorkspaceMemberBlockingReason]


class WorkspaceMembersCapabilitiesApiResponse(ApiModel):
    can_manage_members: bool


class WorkspaceMembersApiResponse(ApiModel):
    workspace_id: UUID
    items: list[WorkspaceMemberItemApiResponse]
    capabilities: WorkspaceMembersCapabilitiesApiResponse


class UpdateWorkspaceMemberRoleApiRequest(ApiRequestModel):
    role: WorkspaceRole
    expected_updated_at: datetime


class TransitionWorkspaceMemberApiRequest(ApiRequestModel):
    expected_updated_at: datetime


class TransferWorkspaceOwnershipApiRequest(ApiRequestModel):
    recipient_member_id: UUID
    expected_workspace_updated_at: datetime
    expected_recipient_updated_at: datetime


class LeaveWorkspaceApiRequest(ApiRequestModel):
    expected_member_updated_at: datetime
    expected_current_workspace_id: UUID


class WorkspaceAuthorityNavigationOutcomeApiResponse(ApiModel):
    kind: Literal["workspace_authority_changed"] = "workspace_authority_changed"
    href: str
    boundary: Literal["hard_reload"] = "hard_reload"


class TransferWorkspaceOwnershipApiResponse(ApiModel):
    members: WorkspaceMembersApiResponse
    session: SessionApiResponse
    navigation_outcome: WorkspaceAuthorityNavigationOutcomeApiResponse


class LeaveWorkspaceApiResponse(ApiModel):
    session: SessionApiResponse
    navigation_outcome: WorkspaceNavigationOutcomeApiResponse
