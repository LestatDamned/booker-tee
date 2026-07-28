"""Calculation and persistence of imported document validation."""

from dataclasses import dataclass

from app.features.imports.application.documents.parse_attempts import (
    latest_parse_attempt,
    statement_control_totals_from_json,
)
from app.features.imports.application.documents.status import transition_document_status
from app.features.imports.domain.control_totals import StatementControlTotals
from app.features.imports.domain.types import UploadedDocumentStatus
from app.features.imports.domain.validation import (
    StatementValidationReport,
    StatementValidationStatus,
    validate_statement_totals,
)
from app.features.imports.models import (
    ParseAttempt,
    ParseAttemptStatus,
    UploadedDocument,
)
from app.features.imports.repository import ImportRepository


@dataclass(frozen=True)
class CalculatedDocumentValidation:
    attempt: ParseAttempt
    control_totals: StatementControlTotals | None
    report: StatementValidationReport


def calculate_document_validation(
    document: UploadedDocument,
) -> CalculatedDocumentValidation | None:
    attempt = latest_parse_attempt(document)
    if attempt is None:
        return None
    control_totals = statement_control_totals_from_json(attempt.control_totals_json)
    return CalculatedDocumentValidation(
        attempt=attempt,
        control_totals=control_totals,
        report=validate_statement_totals(
            rows=document.raw_transactions,
            control_totals=control_totals,
        ),
    )


async def store_import_validation_result(
    imports: ImportRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    *,
    control_totals: StatementControlTotals | None,
    report: StatementValidationReport,
) -> None:
    await imports.store_attempt_validation(
        attempt,
        control_totals=control_totals.as_json() if control_totals else None,
        validation_report=report.as_json(),
    )
    if report.status == StatementValidationStatus.VALID:
        await imports.mark_attempt_status(attempt, ParseAttemptStatus.SUCCESS)
        await transition_document_status(
            imports,
            document,
            UploadedDocumentStatus.PARSED,
        )
        return

    await imports.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
    await transition_document_status(
        imports,
        document,
        UploadedDocumentStatus.REQUIRES_REVIEW,
    )


async def refresh_document_validation(
    imports: ImportRepository,
    document: UploadedDocument,
) -> None:
    validation = calculate_document_validation(document)
    if validation is None:
        return
    await store_import_validation_result(
        imports,
        document,
        validation.attempt,
        control_totals=validation.control_totals,
        report=validation.report,
    )
