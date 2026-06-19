from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.models import RawTransactionStatus


class MoneyDirection(StrEnum):
    INFLOW = "inflow"
    OUTFLOW = "outflow"


@dataclass(frozen=True)
class StatementControlTotals:
    currency: str
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
    total_inflow: Decimal | None = None
    total_outflow: Decimal | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "opening_balance": _decimal_as_string(self.opening_balance),
            "closing_balance": _decimal_as_string(self.closing_balance),
            "total_inflow": _decimal_as_string(self.total_inflow),
            "total_outflow": _decimal_as_string(self.total_outflow),
        }


@dataclass(frozen=True)
class RawTransactionDraft:
    row_index: int
    status: RawTransactionStatus
    raw_payload: dict[str, object]
    operation_date_raw: str | None
    posting_date_raw: str | None
    description_raw: str | None
    amount_raw: str | None
    currency_raw: str | None
    balance_after_raw: str | None
    account_hint_raw: str | None
    account_id: UUID | None
    operation_date: date | None
    posting_date: date | None
    description_normalized: str | None
    amount: Decimal | None
    currency: str | None
    balance_after: Decimal | None
    dedupe_hash: str | None
    confidence_score: Decimal | None
    normalization_error: str | None


class BankStatementRawTransactionParser(Protocol):
    @property
    def bank_code(self) -> str: ...

    @property
    def statement_type(self) -> str: ...

    @property
    def parser_name(self) -> str: ...

    @property
    def parser_version(self) -> str: ...

    def can_parse(self, extracted: ExtractedStatement) -> bool: ...

    def extract_raw_transactions(
        self,
        extracted: ExtractedStatement,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]: ...

    def extract_control_totals(
        self,
        extracted: ExtractedStatement,
        *,
        currency: str,
    ) -> StatementControlTotals | None: ...


def _decimal_as_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01")))
