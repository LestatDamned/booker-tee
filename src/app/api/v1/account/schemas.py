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
