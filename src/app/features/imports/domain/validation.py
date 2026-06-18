from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from app.features.imports.models import RawTransactionStatus
from app.features.imports.parsing.parser_types import StatementControlTotals

MONEY_ZERO = Decimal("0.00")
MONEY_TOLERANCE = Decimal("0.01")


class StatementValidationStatus(StrEnum):
    VALID = "valid"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"
    NEEDS_REVIEW = "needs_review"


class RawTransactionLike(Protocol):
    status: RawTransactionStatus
    amount: Decimal | None
    currency: str | None
    balance_after: Decimal | None


@dataclass(frozen=True)
class RawTransactionTotals:
    extracted_count: int
    calculated_total_inflow: Decimal
    calculated_total_outflow: Decimal
    needs_review_count: int
    currency: str | None

    @property
    def normalized_count(self) -> int:
        return self.extracted_count - self.needs_review_count


@dataclass(frozen=True)
class StatementValidationReport:
    status: StatementValidationStatus
    totals: RawTransactionTotals
    control_totals: StatementControlTotals | None
    balance_chain: "BalanceChainValidationReport"
    inflow_difference: Decimal | None
    outflow_difference: Decimal | None
    message: str

    def as_json(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "currency": self.totals.currency
            or (self.control_totals.currency if self.control_totals else None),
            "extracted_count": self.totals.extracted_count,
            "normalized_count": self.totals.normalized_count,
            "needs_review_count": self.totals.needs_review_count,
            "calculated_total_inflow": _decimal_as_string(self.totals.calculated_total_inflow),
            "calculated_total_outflow": _decimal_as_string(self.totals.calculated_total_outflow),
            "statement_total_inflow": _decimal_as_string(
                self.control_totals.total_inflow if self.control_totals else None
            ),
            "statement_total_outflow": _decimal_as_string(
                self.control_totals.total_outflow if self.control_totals else None
            ),
            "opening_balance": _decimal_as_string(
                self.control_totals.opening_balance if self.control_totals else None
            ),
            "closing_balance": _decimal_as_string(
                self.control_totals.closing_balance if self.control_totals else None
            ),
            "balance_chain": self.balance_chain.as_json(),
            "inflow_difference": _decimal_as_string(self.inflow_difference),
            "outflow_difference": _decimal_as_string(self.outflow_difference),
        }


@dataclass(frozen=True)
class BalanceChainMismatch:
    row_index: int
    previous_row_index: int
    previous_balance_after: Decimal
    previous_amount: Decimal
    amount: Decimal
    expected_balance_after: Decimal
    actual_balance_after: Decimal

    def as_json(self) -> dict[str, object]:
        return {
            "row_index": self.row_index,
            "previous_row_index": self.previous_row_index,
            "previous_balance_after": _decimal_as_string(self.previous_balance_after),
            "previous_amount": _decimal_as_string(self.previous_amount),
            "amount": _decimal_as_string(self.amount),
            "expected_balance_after": _decimal_as_string(self.expected_balance_after),
            "actual_balance_after": _decimal_as_string(self.actual_balance_after),
        }


@dataclass(frozen=True)
class BalanceChainValidationReport:
    status: StatementValidationStatus
    direction: str | None
    checked_pair_count: int
    mismatch_count: int
    mismatches: list[BalanceChainMismatch]

    def as_json(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "direction": self.direction,
            "checked_pair_count": self.checked_pair_count,
            "mismatch_count": self.mismatch_count,
            "mismatches": [mismatch.as_json() for mismatch in self.mismatches],
        }


@dataclass(frozen=True)
class BalanceComparableRow:
    row_index: int
    amount: Decimal
    balance_after: Decimal


def calculate_raw_transaction_totals(
    rows: Sequence[RawTransactionLike],
) -> RawTransactionTotals:
    inflow = MONEY_ZERO
    outflow = MONEY_ZERO
    needs_review_count = 0
    currency: str | None = None

    for row in rows:
        if row.status in {
            RawTransactionStatus.IGNORED,
            RawTransactionStatus.DUPLICATE,
            RawTransactionStatus.FAILED,
        }:
            continue
        if row.currency and currency is None:
            currency = row.currency
        if (
            row.status
            in {RawTransactionStatus.NEEDS_REVIEW, RawTransactionStatus.POSSIBLE_DUPLICATE}
            or row.amount is None
        ):
            needs_review_count += 1
            continue
        if row.amount > MONEY_ZERO:
            inflow += row.amount
        elif row.amount < MONEY_ZERO:
            outflow += abs(row.amount)

    return RawTransactionTotals(
        extracted_count=len(rows),
        calculated_total_inflow=inflow.quantize(MONEY_TOLERANCE),
        calculated_total_outflow=outflow.quantize(MONEY_TOLERANCE),
        needs_review_count=needs_review_count,
        currency=currency,
    )


def validate_statement_totals(
    *,
    rows: Sequence[RawTransactionLike],
    control_totals: StatementControlTotals | None,
) -> StatementValidationReport:
    totals = calculate_raw_transaction_totals(rows)
    balance_chain = validate_balance_chain(rows)
    if totals.needs_review_count:
        return StatementValidationReport(
            status=StatementValidationStatus.NEEDS_REVIEW,
            totals=totals,
            control_totals=control_totals,
            balance_chain=balance_chain,
            inflow_difference=None,
            outflow_difference=None,
            message="Некоторые строки транзакций требуют ручной проверки.",
        )

    if balance_chain.status == StatementValidationStatus.MISMATCH:
        return StatementValidationReport(
            status=StatementValidationStatus.MISMATCH,
            totals=totals,
            control_totals=control_totals,
            balance_chain=balance_chain,
            inflow_difference=None,
            outflow_difference=None,
            message="Остатки после операций не совпадают с суммами строк.",
        )

    if control_totals is None or (
        control_totals.total_inflow is None and control_totals.total_outflow is None
    ):
        return StatementValidationReport(
            status=StatementValidationStatus.UNAVAILABLE,
            totals=totals,
            control_totals=control_totals,
            balance_chain=balance_chain,
            inflow_difference=None,
            outflow_difference=None,
            message="Контрольные итоги выписки недоступны.",
        )

    inflow_difference = _difference(
        totals.calculated_total_inflow,
        control_totals.total_inflow,
    )
    outflow_difference = _difference(
        totals.calculated_total_outflow,
        control_totals.total_outflow,
    )
    if _is_mismatch(inflow_difference) or _is_mismatch(outflow_difference):
        return StatementValidationReport(
            status=StatementValidationStatus.MISMATCH,
            totals=totals,
            control_totals=control_totals,
            balance_chain=balance_chain,
            inflow_difference=inflow_difference,
            outflow_difference=outflow_difference,
            message="Итоги по строкам не совпадают с итогами выписки.",
        )

    return StatementValidationReport(
        status=StatementValidationStatus.VALID,
        totals=totals,
        control_totals=control_totals,
        balance_chain=balance_chain,
        inflow_difference=inflow_difference,
        outflow_difference=outflow_difference,
        message="Итоги по строкам совпадают с итогами выписки.",
    )


def validate_balance_chain(
    rows: Sequence[RawTransactionLike],
) -> BalanceChainValidationReport:
    comparable_pairs = balance_comparable_row_pairs(rows)
    if not comparable_pairs:
        return BalanceChainValidationReport(
            status=StatementValidationStatus.UNAVAILABLE,
            direction=None,
            checked_pair_count=0,
            mismatch_count=0,
            mismatches=[],
        )

    ascending = balance_chain_mismatches(comparable_pairs, direction="ascending")
    descending = balance_chain_mismatches(comparable_pairs, direction="descending")
    if len(ascending) <= len(descending):
        direction = "ascending"
        mismatches = ascending
    else:
        direction = "descending"
        mismatches = descending

    checked_pair_count = len(comparable_pairs)
    if mismatches:
        return BalanceChainValidationReport(
            status=StatementValidationStatus.MISMATCH,
            direction=direction,
            checked_pair_count=checked_pair_count,
            mismatch_count=len(mismatches),
            mismatches=mismatches,
        )

    return BalanceChainValidationReport(
        status=StatementValidationStatus.VALID,
        direction=direction,
        checked_pair_count=checked_pair_count,
        mismatch_count=0,
        mismatches=[],
    )


def balance_comparable_row_pairs(
    rows: Sequence[RawTransactionLike],
) -> list[tuple[BalanceComparableRow, BalanceComparableRow]]:
    pairs: list[tuple[BalanceComparableRow, BalanceComparableRow]] = []
    previous: BalanceComparableRow | None = None
    for row_index, row in enumerate(rows):
        if row.status in {
            RawTransactionStatus.IGNORED,
            RawTransactionStatus.DUPLICATE,
            RawTransactionStatus.FAILED,
        }:
            previous = None
            continue
        if row.amount is None or row.balance_after is None:
            previous = None
            continue
        current = BalanceComparableRow(
            row_index=row_index,
            amount=row.amount,
            balance_after=row.balance_after,
        )
        if previous is not None:
            pairs.append((previous, current))
        previous = current
    return pairs


def balance_chain_mismatches(
    pairs: Sequence[tuple[BalanceComparableRow, BalanceComparableRow]],
    *,
    direction: str,
) -> list[BalanceChainMismatch]:
    mismatches: list[BalanceChainMismatch] = []
    for previous, current in pairs:
        expected = expected_balance_after(
            previous=previous,
            current=current,
            direction=direction,
        )
        if _is_mismatch(_difference(current.balance_after, expected)):
            mismatches.append(
                BalanceChainMismatch(
                    row_index=current.row_index,
                    previous_row_index=previous.row_index,
                    previous_balance_after=previous.balance_after,
                    previous_amount=previous.amount,
                    amount=current.amount,
                    expected_balance_after=expected,
                    actual_balance_after=current.balance_after,
                )
            )
    return mismatches


def expected_balance_after(
    *,
    previous: BalanceComparableRow,
    current: BalanceComparableRow,
    direction: str,
) -> Decimal:
    if direction == "descending":
        return previous.balance_after - previous.amount
    return previous.balance_after + current.amount


def _difference(calculated: Decimal, statement: Decimal | None) -> Decimal | None:
    if statement is None:
        return None
    return (calculated - statement).quantize(MONEY_TOLERANCE)


def _is_mismatch(difference: Decimal | None) -> bool:
    return difference is not None and abs(difference) > MONEY_TOLERANCE


def _decimal_as_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(MONEY_TOLERANCE))
