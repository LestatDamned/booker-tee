from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.features.properties.models import PropertyStatus
from app.shared.schemas import ApplicationModel


class PropertyDirectoryReadonlyReason(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"


class PropertySummaryCapabilitiesDto(ApplicationModel):
    can_update: bool
    can_archive: bool
    can_restore: bool


class PropertySummaryDto(ApplicationModel):
    id: UUID
    name: str
    short_name: str | None
    address: str | None
    status: PropertyStatus
    archived_at: datetime | None
    updated_at: datetime
    capabilities: PropertySummaryCapabilitiesDto


class PropertyDirectoryCapabilitiesDto(ApplicationModel):
    can_create: bool
    readonly_reason_code: PropertyDirectoryReadonlyReason | None


class PropertyDirectoryDto(ApplicationModel):
    items: list[PropertySummaryDto]
    capabilities: PropertyDirectoryCapabilitiesDto
