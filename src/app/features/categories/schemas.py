from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.features.categories.models import CategoryKind
from app.features.ledger.domain.types import OperationType
from app.features.transaction_rules.models import (
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.shared.schemas import ApplicationModel


class CategoryDirectoryReadonlyReason(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"


class CreateCategoryCommand(ApplicationModel):
    name: str
    kind: CategoryKind
    notes: str | None


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


class CategoryDetailFiltersDto(ApplicationModel):
    date_from: date | None
    date_to: date | None
    currency: str
    operation_type: OperationType | None
    search: str | None


class CategoryMoneySummaryDto(ApplicationModel):
    currency: str
    income: Decimal
    expense: Decimal
    profit: Decimal


class CategoryOperationDto(ApplicationModel):
    operation_id: UUID
    operation_date: date
    operation_type: OperationType
    description: str
    account_name: str
    property_id: UUID | None
    property_name: str | None
    signed_amount: Decimal
    currency: str


class CategoryOperationPageDto(ApplicationModel):
    items: list[CategoryOperationDto]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class CategoryRulePreviewItemDto(ApplicationModel):
    id: UUID
    name: str
    is_active: bool
    priority: int
    pattern: str
    match_type: TransactionRuleMatchType
    application_mode: TransactionRuleApplicationMode


class CategoryRulePreviewDto(ApplicationModel):
    items: list[CategoryRulePreviewItemDto]
    total: int
    active_count: int


class CategoryDetailDto(ApplicationModel):
    category: CategorySummaryDto
    applied_filters: CategoryDetailFiltersDto
    available_currencies: list[str]
    summary: CategoryMoneySummaryDto
    operations: CategoryOperationPageDto
    rules: CategoryRulePreviewDto
