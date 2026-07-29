from app.features.imports.documents.lifecycle import transition_document_status
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.types import ParseAttemptStatus
from app.features.imports.domain.control_totals import StatementControlTotals
from app.features.imports.domain.types import UploadedDocumentStatus
from app.features.imports.models import (
    ParseAttempt,
    UploadedDocument,
)


async def mark_attempt_requires_review(
    documents: DocumentRepository,
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
        await documents.store_attempt_validation(
            attempt,
            control_totals=control_totals.as_json(),
            validation_report=report,
        )
        await documents.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
    else:
        await documents.mark_attempt_requires_review(
            attempt,
            message=message,
            validation_report=report,
        )
    await transition_document_status(
        documents,
        document,
        UploadedDocumentStatus.REQUIRES_REVIEW,
    )
