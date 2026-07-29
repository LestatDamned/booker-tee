from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol, cast

from pydantic import SerializerFunctionWrapHandler, computed_field, model_serializer

from app.features.imports.statements.dto import JsonMoney, StatementControlTotals
from app.features.imports.statements.types import RawTransactionStatus
from app.shared.schemas import ApplicationModel

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


class RawTransactionTotals(ApplicationModel):
    extracted_count: int
    calculated_total_inflow: JsonMoney
    calculated_total_outflow: JsonMoney
    ignored_total_inflow: JsonMoney
    ignored_total_outflow: JsonMoney
    needs_review_count: int
    currency: str | None

    @computed_field
    @property
    def normalized_count(self) -> int:
        return self.extracted_count - self.needs_review_count


class StatementValidationReport(ApplicationModel):
    status: StatementValidationStatus
    totals: RawTransactionTotals
    control_totals: StatementControlTotals | None
    balance_chain: "BalanceChainValidationReport"
    inflow_difference: JsonMoney | None
    outflow_difference: JsonMoney | None
    unexplained_inflow_difference: JsonMoney | None
    unexplained_outflow_difference: JsonMoney | None
    message: str

    @model_serializer(mode="wrap")
    def serialize_stored_report(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        values = cast(dict[str, Any], handler(self))
        totals = cast(dict[str, object], values.pop("totals"))
        control_totals = cast(
            dict[str, object],
            values.pop("control_totals") or {},
        )
        return {
            "status": values.pop("status"),
            "message": values.pop("message"),
            "currency": totals.pop("currency") or control_totals.get("currency"),
            **totals,
            "statement_total_inflow": control_totals.get("total_inflow"),
            "statement_total_outflow": control_totals.get("total_outflow"),
            "opening_balance": control_totals.get("opening_balance"),
            "closing_balance": control_totals.get("closing_balance"),
            "balance_chain": values.pop("balance_chain"),
            **values,
        }


class BalanceChainMismatch(ApplicationModel):
    row_index: int
    previous_row_index: int
    previous_balance_after: JsonMoney
    previous_amount: JsonMoney
    amount: JsonMoney
    expected_balance_after: JsonMoney
    actual_balance_after: JsonMoney


class BalanceChainValidationReport(ApplicationModel):
    status: StatementValidationStatus
    direction: str | None
    checked_pair_count: int
    mismatch_count: int
    mismatches: list[BalanceChainMismatch]


class BalanceComparableRow(ApplicationModel):
    row_index: int
    amount: JsonMoney
    balance_after: JsonMoney


def calculate_raw_transaction_totals(
    rows: Sequence[RawTransactionLike],
) -> RawTransactionTotals:
    inflow = MONEY_ZERO
    outflow = MONEY_ZERO
    ignored_inflow = MONEY_ZERO
    ignored_outflow = MONEY_ZERO
    needs_review_count = 0
    currency: str | None = None

    for row in rows:
        if row.currency and currency is None:
            currency = row.currency
        if row.status == RawTransactionStatus.IGNORED:
            if row.amount is not None:
                if row.amount > MONEY_ZERO:
                    ignored_inflow += row.amount
                elif row.amount < MONEY_ZERO:
                    ignored_outflow += abs(row.amount)
            continue
        if row.status in {
            RawTransactionStatus.DUPLICATE,
            RawTransactionStatus.FAILED,
        }:
            continue
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
        ignored_total_inflow=ignored_inflow.quantize(MONEY_TOLERANCE),
        ignored_total_outflow=ignored_outflow.quantize(MONEY_TOLERANCE),
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
            unexplained_inflow_difference=None,
            unexplained_outflow_difference=None,
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
            unexplained_inflow_difference=None,
            unexplained_outflow_difference=None,
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
            unexplained_inflow_difference=None,
            unexplained_outflow_difference=None,
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
    unexplained_inflow_difference = _difference(
        totals.calculated_total_inflow + totals.ignored_total_inflow,
        control_totals.total_inflow,
    )
    unexplained_outflow_difference = _difference(
        totals.calculated_total_outflow + totals.ignored_total_outflow,
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
            unexplained_inflow_difference=unexplained_inflow_difference,
            unexplained_outflow_difference=unexplained_outflow_difference,
            message="Итоги по строкам не совпадают с итогами выписки.",
        )

    return StatementValidationReport(
        status=StatementValidationStatus.VALID,
        totals=totals,
        control_totals=control_totals,
        balance_chain=balance_chain,
        inflow_difference=inflow_difference,
        outflow_difference=outflow_difference,
        unexplained_inflow_difference=unexplained_inflow_difference,
        unexplained_outflow_difference=unexplained_outflow_difference,
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


class StatementValidationReasonCode(StrEnum):
    TOTALS_MATCH = "totals_match"
    ROWS_NEED_REVIEW = "rows_need_review"
    BALANCE_CHAIN_MISMATCH = "balance_chain_mismatch"
    CONTROL_TOTALS_UNAVAILABLE = "control_totals_unavailable"
    CONTROL_TOTALS_MISMATCH = "control_totals_mismatch"
    IGNORED_ROWS_EXPLAIN_MISMATCH = "ignored_rows_explain_mismatch"


def resolve_statement_validation_reason(
    *,
    status: StatementValidationStatus,
    balance_chain_status: StatementValidationStatus | None,
    unexplained_inflow_difference: Decimal | None,
    unexplained_outflow_difference: Decimal | None,
) -> StatementValidationReasonCode:
    if status is StatementValidationStatus.NEEDS_REVIEW:
        return StatementValidationReasonCode.ROWS_NEED_REVIEW
    if balance_chain_status is StatementValidationStatus.MISMATCH:
        return StatementValidationReasonCode.BALANCE_CHAIN_MISMATCH
    if status is StatementValidationStatus.UNAVAILABLE:
        return StatementValidationReasonCode.CONTROL_TOTALS_UNAVAILABLE
    if status is StatementValidationStatus.MISMATCH:
        differences = (
            unexplained_inflow_difference,
            unexplained_outflow_difference,
        )
        comparable = [difference for difference in differences if difference is not None]
        if comparable and all(abs(difference) <= MONEY_TOLERANCE for difference in comparable):
            return StatementValidationReasonCode.IGNORED_ROWS_EXPLAIN_MISMATCH
        return StatementValidationReasonCode.CONTROL_TOTALS_MISMATCH
    return StatementValidationReasonCode.TOTALS_MATCH
