"""Calculation and persistence of imported document validation."""

from dataclasses import dataclass

from app.features.imports.documents.attempts import (
    latest_parse_attempt,
    statement_control_totals_from_json,
)
from app.features.imports.documents.lifecycle import transition_document_status
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.types import ParseAttemptStatus
from app.features.imports.domain.control_totals import StatementControlTotals
from app.features.imports.domain.types import UploadedDocumentStatus
from app.features.imports.domain.validation import (
    StatementValidationReport,
    StatementValidationStatus,
    validate_statement_totals,
)
from app.features.imports.models import (
    ParseAttempt,
    UploadedDocument,
)


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
    documents: DocumentRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    *,
    control_totals: StatementControlTotals | None,
    report: StatementValidationReport,
) -> None:
    await documents.store_attempt_validation(
        attempt,
        control_totals=control_totals.as_json() if control_totals else None,
        validation_report=report.as_json(),
    )
    if report.status == StatementValidationStatus.VALID:
        await documents.mark_attempt_status(attempt, ParseAttemptStatus.SUCCESS)
        await transition_document_status(
            documents,
            document,
            UploadedDocumentStatus.PARSED,
        )
        return

    await documents.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
    await transition_document_status(
        documents,
        document,
        UploadedDocumentStatus.REQUIRES_REVIEW,
    )


async def refresh_document_validation(
    documents: DocumentRepository,
    document: UploadedDocument,
) -> None:
    validation = calculate_document_validation(document)
    if validation is None:
        return
    await store_import_validation_result(
        documents,
        document,
        validation.attempt,
        control_totals=validation.control_totals,
        report=validation.report,
    )
