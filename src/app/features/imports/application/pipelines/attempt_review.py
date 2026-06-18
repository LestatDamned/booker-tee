from app.features.imports.models import (
    ParseAttempt,
    ParseAttemptStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.parsing.parser_types import StatementControlTotals
from app.features.imports.repository import ImportRepository


async def mark_attempt_requires_review(
    imports: ImportRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    message: str,
    validation_report: dict[str, object] | None = None,
    control_totals: StatementControlTotals | None = None,
) -> None:
    report = dict(validation_report or {})
    report.setdefault("message", message)
    report.setdefault("parser_message", message)
    if control_totals is not None:
        await imports.store_attempt_validation(
            attempt,
            control_totals=control_totals.as_json(),
            validation_report=report,
        )
        await imports.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
    else:
        await imports.mark_attempt_requires_review(
            attempt,
            message=message,
            validation_report=report,
        )
    await imports.mark_document_status(document, UploadedDocumentStatus.REQUIRES_REVIEW)
