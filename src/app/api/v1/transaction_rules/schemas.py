from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.api.schemas import ApiModel
from app.features.ledger.models import OperationType
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.schemas import (
    TransactionRuleDeleteBlockedReason,
    TransactionRuleDirectoryReadonlyReason,
    TransactionRuleDirectoryStatus,
    TransactionRuleEnableBlockedReason,
)


class TransactionRuleReferenceApiResponse(ApiModel):
    id: UUID
    name: str
    is_active: bool


class TransactionRuleConditionApiResponse(ApiModel):
    pattern: str
    match_type: TransactionRuleMatchType
    direction: MoneyDirection
    account: TransactionRuleReferenceApiResponse | None
    amount_min: Decimal | None
    amount_max: Decimal | None


class TransactionRuleOutcomeApiResponse(ApiModel):
    operation_type: OperationType | None
    category: TransactionRuleReferenceApiResponse | None
    property: TransactionRuleReferenceApiResponse | None
    application_mode: TransactionRuleApplicationMode
    auto_description: str | None
    affects_profit: bool | None


class TransactionRuleUsageApiResponse(ApiModel):
    direct_raw_suggestion_count: int


class TransactionRuleSummaryCapabilitiesApiResponse(ApiModel):
    can_update: bool
    can_enable: bool
    can_disable: bool
    can_delete: bool
    enable_blocked_reason_code: TransactionRuleEnableBlockedReason | None
    delete_blocked_reason_code: TransactionRuleDeleteBlockedReason | None


class TransactionRuleSummaryApiResponse(ApiModel):
    id: UUID
    name: str
    priority: int
    is_active: bool
    updated_at: datetime
    condition: TransactionRuleConditionApiResponse
    outcome: TransactionRuleOutcomeApiResponse
    usage: TransactionRuleUsageApiResponse
    capabilities: TransactionRuleSummaryCapabilitiesApiResponse


class TransactionRulePageApiResponse(ApiModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class TransactionRuleCountsApiResponse(ApiModel):
    all: int
    active: int
    disabled: int


class TransactionRuleAppliedFiltersApiResponse(ApiModel):
    q: str | None
    category_id: UUID | None
    status: TransactionRuleDirectoryStatus


class TransactionRuleReferencesApiResponse(ApiModel):
    categories: list[TransactionRuleReferenceApiResponse]
    properties: list[TransactionRuleReferenceApiResponse]


class TransactionRuleDirectoryCapabilitiesApiResponse(ApiModel):
    can_create: bool
    can_seed_defaults: bool
    readonly_reason_code: TransactionRuleDirectoryReadonlyReason | None


class TransactionRuleDirectoryApiResponse(ApiModel):
    items: list[TransactionRuleSummaryApiResponse]
    page: TransactionRulePageApiResponse
    counts: TransactionRuleCountsApiResponse
    applied_filters: TransactionRuleAppliedFiltersApiResponse
    references: TransactionRuleReferencesApiResponse
    capabilities: TransactionRuleDirectoryCapabilitiesApiResponse
    target_item: TransactionRuleSummaryApiResponse | None = None


class TransactionRuleCreateApiRequest(ApiModel):
    name: str | None = Field(default=None, max_length=255)
    pattern: str = Field(min_length=1, max_length=255)
    match_type: TransactionRuleMatchType
    direction: MoneyDirection
    amount_min: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    amount_max: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    operation_type: OperationType | None = None
    category_id: UUID | None = None
    property_id: UUID | None = None
    application_mode: TransactionRuleApplicationMode


class TransactionRuleUpdateApiRequest(TransactionRuleCreateApiRequest):
    expected_updated_at: datetime


class TransactionRuleLifecycleApiRequest(ApiModel):
    expected_active: bool
    expected_updated_at: datetime


class TransactionRuleDeleteApiRequest(ApiModel):
    expected_active: bool
    expected_updated_at: datetime


class TransactionRuleCreateApiResponse(ApiModel):
    item: TransactionRuleSummaryApiResponse
    replayed: bool


class TransactionRuleEditApiResponse(ApiModel):
    item: TransactionRuleSummaryApiResponse
    references: TransactionRuleReferencesApiResponse


class TransactionRuleLifecycleImpactApiResponse(ApiModel):
    future_matching_changed: bool
    existing_suggestions_changed: bool
    existing_suggestion_count: int


class TransactionRuleLifecycleApiResponse(ApiModel):
    item: TransactionRuleSummaryApiResponse
    impact: TransactionRuleLifecycleImpactApiResponse


class TransactionRuleDeleteApiResponse(ApiModel):
    deleted_id: UUID
    name: str


class TransactionRuleSeedDefaultsApiResponse(ApiModel):
    created_rules: int
    existing_rules: int
    created_categories: int
