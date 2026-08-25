from dataclasses import dataclass
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.features.imports.mapping.dto import (
    MappedStatementRow,
    UnknownStatementMappingWarning,
    UnsignedAmountDirection,
)
from app.shared.schemas import ApplicationModel


class CoordinateFieldRole(StrEnum):
    OPERATION_DATE = "operation_date"
    POSTING_DATE = "posting_date"
    DESCRIPTION = "description"
    AMOUNT = "amount"
    DEBIT = "debit"
    CREDIT = "credit"
    CURRENCY = "currency"
    BALANCE = "balance"


class CoordinateControlTotalKind(StrEnum):
    OPENING_BALANCE = "opening_balance"
    CLOSING_BALANCE = "closing_balance"
    TOTAL_INFLOW = "total_inflow"
    TOTAL_OUTFLOW = "total_outflow"


class CoordinateModel(ApplicationModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        from_attributes=True,
        frozen=True,
        populate_by_name=True,
    )


class NormalizedRect(CoordinateModel):
    x0: float
    y0: float
    x1: float
    y1: float


class CoordinatePageLayout(CoordinateModel):
    page_aspect_ratio: float = Field(gt=0)
    transaction_top: float
    transaction_bottom: float
    sample_row: NormalizedRect
    fields: dict[CoordinateFieldRole, NormalizedRect]


class CoordinateMappingSpec(CoordinateModel):
    version: Literal[1] = 1
    default_currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    unsigned_amount_direction: UnsignedAmountDirection = UnsignedAmountDirection.REQUIRE_SIGN
    layouts: dict[Literal["first", "middle", "last"], CoordinatePageLayout]

    @field_validator("default_currency", mode="before")
    @classmethod
    def normalize_default_currency(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        currency = value.strip().upper()
        return currency


class CoordinateControlRegion(CoordinateModel):
    kind: CoordinateControlTotalKind
    page_number: int = Field(ge=1)
    rect: NormalizedRect


class CoordinateResolvedControlTotal(CoordinateModel):
    kind: CoordinateControlTotalKind
    page_number: int
    raw_value: str
    amount: str | None
    error: str | None = None


class CoordinateReconciliationCheck(CoordinateModel):
    kind: Literal["balance", "total_inflow", "total_outflow"]
    expected: str
    actual: str
    difference: str
    matches: bool


class CoordinateTemplateSnapshot(CoordinateModel):
    id: UUID
    name: str
    spec: CoordinateMappingSpec


class CoordinatePageMetadata(CoordinateModel):
    page_number: int
    width: float
    height: float
    aspect_ratio: float
    has_text_layer: bool


class CoordinateCapability(CoordinateModel):
    allowed: bool
    blocking_reason_codes: tuple[str, ...]


class CoordinateMappingOverview(CoordinateModel):
    document_id: UUID
    filename: str
    page_count: int
    pages: tuple[CoordinatePageMetadata, ...]
    default_currency: str
    capability: CoordinateCapability
    templates: tuple[CoordinateTemplateSnapshot, ...]


class CoordinatePreviewRow(CoordinateModel):
    page_number: int
    source_row_number: int
    layout: Literal["first", "middle", "last"]
    operation_date_raw: str
    operation_date: str | None
    posting_date_raw: str
    posting_date: str | None
    description_raw: str
    description: str
    amount_raw: str
    amount: str | None
    currency_raw: str
    currency: str
    balance_after_raw: str
    balance_after: str | None
    status: Literal["valid", "error"]
    errors: tuple[str, ...]


class CoordinatePreview(CoordinateModel):
    rows: tuple[CoordinatePreviewRow, ...]
    total_row_count: int
    valid_row_count: int
    invalid_row_count: int
    row_limit: int
    rows_truncated: bool
    warnings: tuple[UnknownStatementMappingWarning, ...]
    control_totals: tuple[CoordinateResolvedControlTotal, ...] = ()
    reconciliation: tuple[CoordinateReconciliationCheck, ...] = ()
    can_import: bool


@dataclass(frozen=True)
class CoordinateExtractionResult:
    rows: list[MappedStatementRow]
    layouts: list[Literal["first", "middle", "last"]]
    warnings: list[UnknownStatementMappingWarning]
