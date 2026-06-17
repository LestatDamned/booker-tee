from uuid import UUID

from pdfplumber.utils.exceptions import PdfminerException

from app.db.base import utc_now
from app.features.imports.models import ParseAttempt, UploadedDocument, UploadedDocumentStatus
from app.features.imports.repository import ImportRepository

PARSER_EXCEPTIONS = (OSError, ValueError, TypeError, PdfminerException)


async def create_running_parse_attempt(
    imports: ImportRepository,
    *,
    workspace_id: UUID,
    document_id: UUID,
) -> ParseAttempt:
    attempt = ParseAttempt(
        workspace_id=workspace_id,
        uploaded_document_id=document_id,
        parser_name="auto_statement_parser",
        parser_version=None,
    )
    return await imports.create_parse_attempt(attempt)


async def record_failed_parse_attempt(
    imports: ImportRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    exc: OSError | ValueError | TypeError | PdfminerException,
    *,
    document_status: UploadedDocumentStatus = UploadedDocumentStatus.FAILED_TO_PARSE,
) -> None:
    attempt.finished_at = utc_now()
    await imports.mark_attempt_failed(
        attempt,
        error_code=type(exc).__name__,
        error_message=sanitize_error_message(exc),
    )
    await imports.mark_document_status(document, document_status)


def sanitize_error_message(exc: BaseException) -> str:
    message = str(exc).strip()
    if not message:
        return type(exc).__name__
    return f"{type(exc).__name__}: {message[:300]}"
