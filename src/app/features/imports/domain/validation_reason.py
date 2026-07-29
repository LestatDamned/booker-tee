"""Stable reason codes derived from statement validation facts."""

from decimal import Decimal
from enum import StrEnum

from app.features.imports.domain.validation import (
    MONEY_TOLERANCE,
    StatementValidationStatus,
)


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
