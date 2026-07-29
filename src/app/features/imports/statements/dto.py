from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.imports.statements.types import RawTransactionStatus


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


@dataclass(frozen=True)
class StatementControlTotals:
    currency: str | None
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


def _decimal_as_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01")))
