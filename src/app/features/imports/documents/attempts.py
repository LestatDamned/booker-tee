from uuid import UUID, uuid4

from openpyxl.utils.exceptions import InvalidFileException
from pdfplumber.utils.exceptions import PdfminerException

from app.db.base import utc_now
from app.features.imports.documents.lifecycle import transition_document_status
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.types import ParseAttemptStatus, UploadedDocumentStatus
from app.features.imports.documents.validation_report import StoredValidationReport
from app.features.imports.models import ParseAttempt, UploadedDocument
from app.features.imports.parsers.sidecar.protocol import ParserSidecarError
from app.features.imports.statements.dto import StatementControlTotals

PARSER_EXCEPTIONS = (OSError, ValueError, TypeError, PdfminerException, InvalidFileException)


async def create_running_parse_attempt(
    documents: DocumentRepository,
    *,
    workspace_id: UUID,
    document_id: UUID,
    attempt_id: UUID | None = None,
) -> ParseAttempt:
    attempt = ParseAttempt(
        id=attempt_id or uuid4(),
        workspace_id=workspace_id,
        uploaded_document_id=document_id,
        parser_name="auto_statement_parser",
        parser_version=None,
    )
    return await documents.create_parse_attempt(attempt)


async def record_failed_parse_attempt(
    documents: DocumentRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    exc: BaseException,
    *,
    document_status: UploadedDocumentStatus = UploadedDocumentStatus.FAILED_TO_PARSE,
) -> None:
    attempt.finished_at = utc_now()
    await documents.mark_attempt_failed(
        attempt,
        error_code=(str(exc.code) if isinstance(exc, ParserSidecarError) else type(exc).__name__),
        error_message=sanitize_error_message(exc),
    )
    await transition_document_status(documents, document, document_status)


async def mark_attempt_requires_review(
    documents: DocumentRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    message: str,
    validation_report: StoredValidationReport | None = None,
    control_totals: StatementControlTotals | None = None,
) -> None:
    report = (
        validation_report.model_dump(mode="json", exclude_unset=True)
        if validation_report is not None
        else {}
    )
    report.setdefault("message", message)
    report.setdefault("parser_message", message)
    if control_totals is not None:
        await documents.store_attempt_validation(
            attempt,
            control_totals=control_totals.model_dump(mode="json"),
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


def sanitize_error_message(exc: BaseException) -> str:
    if isinstance(exc, ParserSidecarError):
        return str(exc.code)
    return type(exc).__name__


def latest_parse_attempt(document: UploadedDocument) -> ParseAttempt | None:
    attempts = getattr(document, "parse_attempts", ())
    if not attempts:
        return None
    return max(attempts, key=lambda attempt: attempt.started_at)
