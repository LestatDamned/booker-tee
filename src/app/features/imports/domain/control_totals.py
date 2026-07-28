from dataclasses import dataclass
from decimal import Decimal


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


def _decimal_as_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01")))
