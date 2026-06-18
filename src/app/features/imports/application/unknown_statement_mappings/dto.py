from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class UnknownStatementMappingCommand:
    page_number: int
    table_index: int
    operation_date_column: int
    description_column: int
    amount_column: int | None
    currency_column: int | None
    first_data_row: int
    default_currency: str
    posting_date_column: int | None = None
    debit_amount_column: int | None = None
    credit_amount_column: int | None = None
    balance_after_column: int | None = None


@dataclass(frozen=True)
class SaveImportMappingTemplateCommand:
    name: str
    bank_name: str | None
    statement_type: str | None
    mapping: UnknownStatementMappingCommand


@dataclass(frozen=True)
class UnknownStatementMappedRow:
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
    status: str
    error: str
    posting_date_raw: str = ""
    posting_date: date | None = None
    balance_after_raw: str = ""
    balance_after: Decimal | None = None


@dataclass(frozen=True)
class UnknownStatementMappingWarning:
    code: str
    severity: str
    fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UnknownStatementMappingPreview:
    rows: list[UnknownStatementMappedRow]
    warnings: list[UnknownStatementMappingWarning] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "valid")

    @property
    def error_count(self) -> int:
        return sum(1 for row in self.rows if row.status == "error")
