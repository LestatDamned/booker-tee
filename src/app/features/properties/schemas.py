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


class CreatePropertyCommand(ApplicationModel):
    name: str
    short_name: str | None
    address: str | None


class UpdatePropertyCommand(CreatePropertyCommand):
    expected_updated_at: datetime


class PropertyLifecycleCommand(ApplicationModel):
    expected_status: PropertyStatus
    expected_updated_at: datetime


class PropertyLifecycleImpactDto(ApplicationModel):
    history_preserved: bool
    active_rules_unchanged: bool
    available_for_new_references: bool


class PropertyLifecycleResultDto(ApplicationModel):
    property: PropertySummaryDto
    impact: PropertyLifecycleImpactDto
