"""Review projection of statement validation results."""

from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.imports.statements.validation import (
    StatementValidationReport,
    StatementValidationStatus,
    resolve_statement_validation_reason,
)
from app.features.imports.statements.validation_service import StatementValidationService
from app.shared.schemas import ApplicationModel


class ImportReviewValidationReasonCode(StrEnum):
    TOTALS_MATCH = "totals_match"
    ROWS_NEED_REVIEW = "rows_need_review"
    BALANCE_CHAIN_MISMATCH = "balance_chain_mismatch"
    CONTROL_TOTALS_UNAVAILABLE = "control_totals_unavailable"
    CONTROL_TOTALS_MISMATCH = "control_totals_mismatch"
    IGNORED_ROWS_EXPLAIN_MISMATCH = "ignored_rows_explain_mismatch"


class ImportReviewRowProblemCode(StrEnum):
    BALANCE_CHAIN_MISMATCH = "balance_chain_mismatch"


class ImportReviewBalanceChainDto(ApplicationModel):
    status: StatementValidationStatus
    direction: str | None
    checked_pair_count: int
    mismatch_count: int


class ImportReviewRowProblemDto(ApplicationModel):
    item_id: UUID
    row_index: int
    previous_item_id: UUID
    previous_row_index: int
    code: ImportReviewRowProblemCode
    expected_balance_after: Decimal
    actual_balance_after: Decimal


class ImportReviewValidationDto(ApplicationModel):
    status: StatementValidationStatus
    reason_code: ImportReviewValidationReasonCode
    currency: str | None
    extracted_count: int
    normalized_count: int
    needs_review_count: int
    calculated_total_inflow: Decimal
    calculated_total_outflow: Decimal
    ignored_total_inflow: Decimal
    ignored_total_outflow: Decimal
    statement_total_inflow: Decimal | None
    statement_total_outflow: Decimal | None
    opening_balance: Decimal | None
    closing_balance: Decimal | None
    inflow_difference: Decimal | None
    outflow_difference: Decimal | None
    unexplained_inflow_difference: Decimal | None
    unexplained_outflow_difference: Decimal | None
    balance_chain: ImportReviewBalanceChainDto
    row_problems: tuple[ImportReviewRowProblemDto, ...]


def build_import_review_validation(
    document: UploadedDocument,
) -> ImportReviewValidationDto | None:
    calculated = StatementValidationService.calculate_for_document(document)
    if calculated is None:
        return None
    report = calculated.report
    control_totals = report.control_totals
    return ImportReviewValidationDto(
        status=report.status,
        reason_code=ImportReviewValidationReasonCode(
            resolve_statement_validation_reason(
                status=report.status,
                balance_chain_status=report.balance_chain.status,
                unexplained_inflow_difference=report.unexplained_inflow_difference,
                unexplained_outflow_difference=report.unexplained_outflow_difference,
            ).value
        ),
        currency=report.totals.currency or (control_totals.currency if control_totals else None),
        extracted_count=report.totals.extracted_count,
        normalized_count=report.totals.normalized_count,
        needs_review_count=report.totals.needs_review_count,
        calculated_total_inflow=report.totals.calculated_total_inflow,
        calculated_total_outflow=report.totals.calculated_total_outflow,
        ignored_total_inflow=report.totals.ignored_total_inflow,
        ignored_total_outflow=report.totals.ignored_total_outflow,
        statement_total_inflow=(control_totals.total_inflow if control_totals else None),
        statement_total_outflow=(control_totals.total_outflow if control_totals else None),
        opening_balance=(control_totals.opening_balance if control_totals else None),
        closing_balance=(control_totals.closing_balance if control_totals else None),
        inflow_difference=report.inflow_difference,
        outflow_difference=report.outflow_difference,
        unexplained_inflow_difference=report.unexplained_inflow_difference,
        unexplained_outflow_difference=report.unexplained_outflow_difference,
        balance_chain=ImportReviewBalanceChainDto(
            status=report.balance_chain.status,
            direction=report.balance_chain.direction,
            checked_pair_count=report.balance_chain.checked_pair_count,
            mismatch_count=report.balance_chain.mismatch_count,
        ),
        row_problems=_row_problems(document.raw_transactions, report),
    )


def _row_problems(
    rows: list[RawTransaction],
    report: StatementValidationReport,
) -> tuple[ImportReviewRowProblemDto, ...]:
    problems: list[ImportReviewRowProblemDto] = []
    for mismatch in report.balance_chain.mismatches:
        if mismatch.row_index >= len(rows) or mismatch.previous_row_index >= len(rows):
            continue
        row = rows[mismatch.row_index]
        previous = rows[mismatch.previous_row_index]
        problems.append(
            ImportReviewRowProblemDto(
                item_id=row.id,
                row_index=row.row_index,
                previous_item_id=previous.id,
                previous_row_index=previous.row_index,
                code=ImportReviewRowProblemCode.BALANCE_CHAIN_MISMATCH,
                expected_balance_after=mismatch.expected_balance_after,
                actual_balance_after=mismatch.actual_balance_after,
            )
        )
    return tuple(problems)
