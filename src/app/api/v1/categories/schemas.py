from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from app.api.schemas import ApiModel, ApiRequestModel
from app.features.categories.models import CategoryKind
from app.features.categories.schemas import (
    CategoryArchiveBlockedReason,
    CategoryDirectoryReadonlyReason,
)
from app.features.ledger.domain.types import OperationType
from app.features.transaction_rules.models import (
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
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


class CreateCategoryApiRequest(ApiRequestModel):
    name: str = Field(max_length=255)
    kind: CategoryKind
    notes: str | None = Field(default=None, max_length=1000)

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
                "category_name_required",
                "Название категории обязательно.",
            )
        return name

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, value: object) -> object:
        if isinstance(value, str):
            return " ".join(value.split()) or None
        return value


class CategoryDetailFiltersApiResponse(ApiModel):
    date_from: date | None
    date_to: date | None
    currency: str
    operation_type: OperationType | None
    search: str | None


class CategoryMoneySummaryApiResponse(ApiModel):
    currency: str
    income: str
    expense: str
    profit: str


class CategoryOperationApiResponse(ApiModel):
    operation_id: UUID
    operation_date: date
    operation_type: OperationType
    description: str
    account_name: str
    property_id: UUID | None
    property_name: str | None
    signed_amount: str
    currency: str


class CategoryOperationPageApiResponse(ApiModel):
    items: list[CategoryOperationApiResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class CategoryRulePreviewItemApiResponse(ApiModel):
    id: UUID
    name: str
    is_active: bool
    priority: int
    pattern: str
    match_type: TransactionRuleMatchType
    application_mode: TransactionRuleApplicationMode


class CategoryRulePreviewApiResponse(ApiModel):
    items: list[CategoryRulePreviewItemApiResponse]
    total: int
    active_count: int


class CategoryDetailApiResponse(ApiModel):
    category: CategorySummaryApiResponse
    applied_filters: CategoryDetailFiltersApiResponse
    available_currencies: list[str]
    summary: CategoryMoneySummaryApiResponse
    operations: CategoryOperationPageApiResponse
    rules: CategoryRulePreviewApiResponse
