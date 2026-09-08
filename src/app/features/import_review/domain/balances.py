"""Statement balance comparison; never an account's ledger balance."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.features.imports.statements.types import RawTransactionStatus
from app.features.imports.statements.validation import (
    RawTransactionLike,
    StatementValidationReport,
)

type BalanceComparisonStatus = Literal[
    "match", "explained", "mismatch", "unavailable", "needs_review"
]


@dataclass(frozen=True)
class StatementBalanceComparison:
    calculated_closing_balance: Decimal | None = None
    balance_difference: Decimal | None = None
    balance_status: BalanceComparisonStatus = "unavailable"

    @classmethod
    def calculate(
        cls, report: StatementValidationReport, rows: Sequence[RawTransactionLike]
    ) -> "StatementBalanceComparison":
        control = report.control_totals
        if control is None or control.opening_balance is None:
            return cls()
        relevant = [row for row in rows if row.status != RawTransactionStatus.DUPLICATE]
        if report.totals.needs_review_count or any(
            row.amount is None or row.status == RawTransactionStatus.FAILED for row in relevant
        ):
            return cls(balance_status="needs_review")
        currencies = {row.currency for row in relevant}
        if (
            None in currencies
            or len(currencies) > 1
            or (control.currency and currencies and currencies != {control.currency})
        ):
            return cls()
        totals = report.totals
        closing = (
            control.opening_balance
            + totals.calculated_total_inflow
            - totals.calculated_total_outflow
        )
        if control.closing_balance is None:
            return cls(calculated_closing_balance=closing)
        difference = closing - control.closing_balance
        if difference == 0:
            status: BalanceComparisonStatus = "match"
        elif difference + totals.ignored_total_inflow - totals.ignored_total_outflow == 0:
            status = "explained"
        else:
            status = "mismatch"
        return cls(closing, difference, status)
