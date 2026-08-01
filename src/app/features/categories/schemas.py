from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.features.categories.models import CategoryKind
from app.shared.schemas import ApplicationModel


class CategoryDirectoryReadonlyReason(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"


class CategoryArchiveBlockedReason(StrEnum):
    ACTIVE_RULES = "active_rules"


class CategorySummaryCapabilitiesDto(ApplicationModel):
    can_update: bool
    can_archive: bool
    can_restore: bool
    archive_blocked_reason_code: CategoryArchiveBlockedReason | None


class CategorySummaryDto(ApplicationModel):
    id: UUID
    name: str
    kind: CategoryKind
    is_active: bool
    is_system: bool
    system_key: str | None
    notes: str | None
    operation_count: int
    rule_count: int
    active_rule_count: int
    updated_at: datetime
    capabilities: CategorySummaryCapabilitiesDto


class CategoryKindOptionDto(ApplicationModel):
    value: CategoryKind
    label: str
    description: str


class CategoryDirectoryCapabilitiesDto(ApplicationModel):
    can_create: bool
    readonly_reason_code: CategoryDirectoryReadonlyReason | None


class CategoryDirectoryDto(ApplicationModel):
    items: list[CategorySummaryDto]
    kind_options: list[CategoryKindOptionDto]
    capabilities: CategoryDirectoryCapabilitiesDto
