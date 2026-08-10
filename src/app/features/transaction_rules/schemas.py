from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.features.ledger.models import OperationType
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.shared.schemas import ApplicationModel


class TransactionRuleDirectoryStatus(StrEnum):
    ALL = "all"
    ACTIVE = "active"
    DISABLED = "disabled"


class TransactionRuleDirectoryReadonlyReason(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"


class TransactionRuleEnableBlockedReason(StrEnum):
    CATEGORY_INACTIVE = "category_inactive"
    PROPERTY_ARCHIVED = "property_archived"
    ACCOUNT_UNAVAILABLE = "account_unavailable"


class TransactionRuleDeleteBlockedReason(StrEnum):
    ACTIVE_RULE = "active_rule"
    RAW_SUGGESTIONS = "raw_suggestions"


class TransactionRuleReferenceDto(ApplicationModel):
    id: UUID
    name: str
    is_active: bool


class TransactionRuleConditionDto(ApplicationModel):
    pattern: str
    match_type: TransactionRuleMatchType
    direction: MoneyDirection
    account: TransactionRuleReferenceDto | None
    amount_min: Decimal | None
    amount_max: Decimal | None


class TransactionRuleOutcomeDto(ApplicationModel):
    operation_type: OperationType | None
    category: TransactionRuleReferenceDto | None
    property: TransactionRuleReferenceDto | None
    application_mode: TransactionRuleApplicationMode
    auto_description: str | None
    affects_profit: bool | None


class TransactionRuleUsageDto(ApplicationModel):
    direct_raw_suggestion_count: int


class TransactionRuleSummaryCapabilitiesDto(ApplicationModel):
    can_update: bool
    can_enable: bool
    can_disable: bool
    can_delete: bool
    enable_blocked_reason_code: TransactionRuleEnableBlockedReason | None
    delete_blocked_reason_code: TransactionRuleDeleteBlockedReason | None


class TransactionRuleSummaryDto(ApplicationModel):
    id: UUID
    name: str
    priority: int
    is_active: bool
    updated_at: datetime
    condition: TransactionRuleConditionDto
    outcome: TransactionRuleOutcomeDto
    usage: TransactionRuleUsageDto
    capabilities: TransactionRuleSummaryCapabilitiesDto


class TransactionRulePageDto(ApplicationModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class TransactionRuleCountsDto(ApplicationModel):
    all: int
    active: int
    disabled: int


class TransactionRuleAppliedFiltersDto(ApplicationModel):
    q: str | None
    category_id: UUID | None
    status: TransactionRuleDirectoryStatus


class TransactionRuleReferencesDto(ApplicationModel):
    categories: list[TransactionRuleReferenceDto]
    properties: list[TransactionRuleReferenceDto]


class TransactionRuleDirectoryCapabilitiesDto(ApplicationModel):
    can_create: bool
    can_seed_defaults: bool
    readonly_reason_code: TransactionRuleDirectoryReadonlyReason | None


class TransactionRuleDirectoryDto(ApplicationModel):
    items: list[TransactionRuleSummaryDto]
    page: TransactionRulePageDto
    counts: TransactionRuleCountsDto
    applied_filters: TransactionRuleAppliedFiltersDto
    references: TransactionRuleReferencesDto
    capabilities: TransactionRuleDirectoryCapabilitiesDto
    target_item: TransactionRuleSummaryDto | None = None
