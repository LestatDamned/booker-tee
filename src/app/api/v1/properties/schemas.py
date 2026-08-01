from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from app.api.schemas import ApiModel, ApiRequestModel
from app.features.properties.models import PropertyStatus
from app.features.properties.schemas import PropertyDirectoryReadonlyReason


class PropertySummaryCapabilitiesApiResponse(ApiModel):
    can_update: bool
    can_archive: bool
    can_restore: bool


class PropertySummaryApiResponse(ApiModel):
    id: UUID
    name: str
    short_name: str | None
    address: str | None
    status: PropertyStatus
    archived_at: datetime | None
    updated_at: datetime
    capabilities: PropertySummaryCapabilitiesApiResponse


class PropertyDirectoryCapabilitiesApiResponse(ApiModel):
    can_create: bool
    readonly_reason_code: PropertyDirectoryReadonlyReason | None


class PropertyDirectoryApiResponse(ApiModel):
    items: list[PropertySummaryApiResponse]
    capabilities: PropertyDirectoryCapabilitiesApiResponse


class CreatePropertyApiRequest(ApiRequestModel):
    name: str = Field(max_length=255)
    short_name: str | None = Field(default=None, max_length=64)
    address: str | None = None

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
                "property_name_required",
                "Название объекта обязательно.",
            )
        return name

    @field_validator("short_name", "address", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            return " ".join(value.split()) or None
        return value
