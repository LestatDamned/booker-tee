from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from app.features.imports.documents.types import UploadedDocumentStatus
from app.shared.schemas import ApplicationModel


class UnsignedAmountDirection(StrEnum):
    REQUIRE_SIGN = "require_sign"
    INCOME = "income"
    EXPENSE = "expense"


class MappingDefaultSource(StrEnum):
    TEMPLATE = "template"
    ANALYZER = "analyzer"
    FALLBACK = "fallback"


class MappingControlTotalKind(StrEnum):
    OPENING_BALANCE = "opening_balance"
    CLOSING_BALANCE = "closing_balance"


class MappingBlockingReasonCode(StrEnum):
    ACCOUNT_REQUIRED = "account_required"
    RAW_TABLES_UNAVAILABLE = "raw_tables_unavailable"
    MAPPING_NOT_REQUIRED = "mapping_not_required"
    CONFIRMED_ROWS_EXIST = "confirmed_rows_exist"


class MappingRowErrorCode(StrEnum):
    OPERATION_DATE_REQUIRED = "operation_date_required"
    OPERATION_DATE_INVALID = "operation_date_invalid"
    POSTING_DATE_INVALID = "posting_date_invalid"
    AMOUNT_REQUIRED = "amount_required"
    AMOUNT_INVALID = "amount_invalid"
    UNSIGNED_AMOUNT_DIRECTION_REQUIRED = "unsigned_amount_direction_required"
    DEBIT_INVALID = "debit_invalid"
    CREDIT_INVALID = "credit_invalid"
    DEBIT_AND_CREDIT_PRESENT = "debit_and_credit_present"
    BALANCE_AFTER_INVALID = "balance_after_invalid"
    DESCRIPTION_REQUIRED = "description_required"


class MappingControlTotalCellRef(ApplicationModel):
    page_number: int
    table_index: int
    row_number: int
    column_index: int


class StatementMappingSpec(ApplicationModel):
    model_config = ConfigDict(extra="ignore")

    page_number: int = 1
    table_index: int = 0
    operation_date_column: int = 0
    description_column: int = 2
    amount_column: int | None = None
    currency_column: int | None = None
    first_data_row: int = 1
    default_currency: str
    unsigned_amount_direction: UnsignedAmountDirection = UnsignedAmountDirection.REQUIRE_SIGN
    posting_date_column: int | None = None
    debit_amount_column: int | None = None
    credit_amount_column: int | None = None
    balance_after_column: int | None = None
    opening_balance_cell: MappingControlTotalCellRef | None = Field(
        default=None,
        exclude=True,
    )
    closing_balance_cell: MappingControlTotalCellRef | None = Field(
        default=None,
        exclude=True,
    )


class MappingTemplateSnapshot(ApplicationModel):
    id: UUID
    name: str
    bank_name: str | None
    statement_type: str | None
    default_currency: str
    mapping: StatementMappingSpec
    table_signature: dict[str, object] | None = None


class ResolvedMappingDefault(ApplicationModel):
    spec: StatementMappingSpec
    source: MappingDefaultSource
    template_id: UUID | None


@dataclass(frozen=True)
class MappedStatementRow:
    page_number: int
    table_index: int
    source_row_number: int
    operation_date_raw: str
    operation_date: date | None
    description_raw: str
    description: str | None
    amount_raw: str
    amount: Decimal | None
    currency_raw: str
    currency: str
    status: Literal["valid", "error"]
    error: str
    posting_date_raw: str = ""
    posting_date: date | None = None
    balance_after_raw: str = ""
    balance_after: Decimal | None = None


@dataclass(frozen=True)
class UnknownStatementMappingWarning:
    code: str
    severity: Literal["warning", "error"]
    fields: list[str] = field(default_factory=list)
    affected_row_count: int | None = None


@dataclass(frozen=True)
class StatementMappingResult:
    rows: list[MappedStatementRow]
    warnings: list[UnknownStatementMappingWarning] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "valid")

    @property
    def error_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "error")


class StatementMappingImportResult(ApplicationModel):
    document_id: UUID
    document_status: UploadedDocumentStatus
    imported_row_count: int
    template_id: UUID | None
    replayed: bool
