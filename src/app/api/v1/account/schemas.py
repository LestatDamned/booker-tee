from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel, ApiRequestModel


class AccountApiResponse(ApiModel):
    id: UUID
    email: str
    name: str | None


class UpdateAccountApiRequest(ApiRequestModel):
    name: str | None = Field(default=None, max_length=255)


class ChangePasswordApiRequest(ApiRequestModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(max_length=1024)


class ChangePasswordApiResponse(ApiModel):
    message: str


class UserSessionApiResponse(ApiModel):
    id: UUID
    is_current: bool
    device_summary: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime


class UserSessionListApiResponse(ApiModel):
    items: list[UserSessionApiResponse]


class RevokeOtherSessionsApiResponse(ApiModel):
    revoked_count: int


class RequestEmailChangeApiRequest(ApiRequestModel):
    target_email: str = Field(min_length=3, max_length=320)
    current_password: str = Field(max_length=1024)


class ConfirmEmailChangeApiRequest(ApiRequestModel):
    token: str = Field(min_length=1, max_length=1024)


class EmailChangeApiResponse(ApiModel):
    message: str
    email: str | None = None


class DeactivationBlockerApiResponse(ApiModel):
    workspace_id: UUID
    workspace_name: str
    active_other_member_count: int


class AccountDeactivationImpactApiResponse(ApiModel):
    can_deactivate: bool
    blockers: list[DeactivationBlockerApiResponse]
    auto_deactivated_workspace_count: int


class DeactivateAccountApiRequest(ApiRequestModel):
    current_password: str = Field(max_length=1024)
    confirmation: str = Field(max_length=64)


class DeactivateAccountApiResponse(ApiModel):
    message: str
