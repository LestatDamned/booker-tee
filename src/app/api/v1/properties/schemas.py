from datetime import datetime
from uuid import UUID

from app.api.schemas import ApiModel
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
