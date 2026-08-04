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
