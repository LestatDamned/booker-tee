from datetime import datetime
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.categories.models import CategoryKind
from app.features.categories.schemas import (
    CategoryArchiveBlockedReason,
    CategoryDirectoryReadonlyReason,
)


class CategorySummaryCapabilitiesApiResponse(ApiModel):
    can_update: bool
    can_archive: bool
    can_restore: bool
    archive_blocked_reason_code: CategoryArchiveBlockedReason | None


class CategorySummaryApiResponse(ApiModel):
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
    capabilities: CategorySummaryCapabilitiesApiResponse


class CategoryKindOptionApiResponse(ApiModel):
    value: CategoryKind
    label: str
    description: str


class CategoryDirectoryCapabilitiesApiResponse(ApiModel):
    can_create: bool
    readonly_reason_code: CategoryDirectoryReadonlyReason | None


class CategoryDirectoryApiResponse(ApiModel):
    items: list[CategorySummaryApiResponse]
    kind_options: list[CategoryKindOptionApiResponse]
    capabilities: CategoryDirectoryCapabilitiesApiResponse
