from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel, ApiRequestModel


class AccountApiResponse(ApiModel):
    id: UUID
    email: str
    name: str | None


class UpdateAccountApiRequest(ApiRequestModel):
    name: str | None = Field(default=None, max_length=255)
