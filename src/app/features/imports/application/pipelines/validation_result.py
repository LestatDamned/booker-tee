from app.features.imports.domain.validation import (
    StatementValidationReport,
    StatementValidationStatus,
)
from app.features.imports.models import (
    ParseAttempt,
    ParseAttemptStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.parsing.parser_types import StatementControlTotals
from app.features.imports.repository import ImportRepository


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
        await imports.mark_document_status(document, UploadedDocumentStatus.PARSED)
        return

    await imports.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
    await imports.mark_document_status(document, UploadedDocumentStatus.REQUIRES_REVIEW)
