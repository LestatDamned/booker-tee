from collections.abc import Iterable
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus

if TYPE_CHECKING:
    from app.features.imports.documents.repository import DocumentRepository

COMPLETE_RAW_TRANSACTION_STATUSES = frozenset(
    {
        RawTransactionStatus.CONFIRMED,
        RawTransactionStatus.IGNORED,
        RawTransactionStatus.DUPLICATE,
    }
)

_ALLOWED_DOCUMENT_STATUS_TRANSITIONS = {
    UploadedDocumentStatus.UPLOADED: frozenset(
        {
            UploadedDocumentStatus.PENDING_PARSE,
            UploadedDocumentStatus.PARSING,
            UploadedDocumentStatus.PARSED,
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.FAILED_TO_PARSE,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.PENDING_PARSE: frozenset(
        {
            UploadedDocumentStatus.PARSING,
            UploadedDocumentStatus.PARSED,
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.FAILED_TO_PARSE,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.PARSING: frozenset(
        {
            UploadedDocumentStatus.PARSED,
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.FAILED_TO_PARSE,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.PARSED: frozenset(
        {
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.IMPORTED,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.REQUIRES_REVIEW: frozenset(
        {
            UploadedDocumentStatus.IMPORTED,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.FAILED_TO_PARSE: frozenset(
        {
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.IMPORTED: frozenset(
        {
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.IGNORED: frozenset(
        {
            UploadedDocumentStatus.REQUIRES_REVIEW,
        }
    ),
}


class DocumentLifecycleError(ValueError):
    pass


class LinkedOperationSource(Protocol):
    @property
    def linked_operation_id(self) -> UUID | None: ...


def resolve_document_status_transition(
    *,
    current_status: UploadedDocumentStatus,
    target_status: UploadedDocumentStatus,
) -> UploadedDocumentStatus:
    if target_status not in allowed_document_status_transitions(current_status):
        raise DocumentLifecycleError(
            f"Document status cannot change from {current_status.value} to {target_status.value}."
        )
    return target_status


def allowed_document_status_transitions(
    current_status: UploadedDocumentStatus,
) -> frozenset[UploadedDocumentStatus]:
    return _ALLOWED_DOCUMENT_STATUS_TRANSITIONS[current_status] | {current_status}


def resolve_document_review_status(
    row_statuses: Iterable[RawTransactionStatus],
) -> UploadedDocumentStatus | None:
    statuses = tuple(row_statuses)
    if not statuses:
        return None
    if all(status in COMPLETE_RAW_TRANSACTION_STATUSES for status in statuses):
        return UploadedDocumentStatus.IMPORTED
    return UploadedDocumentStatus.REQUIRES_REVIEW


def has_linked_operations(rows: Iterable[LinkedOperationSource]) -> bool:
    return any(row.linked_operation_id is not None for row in rows)


class ImportedDocumentStatusUpdater:
    def __init__(self, documents: "DocumentRepository") -> None:
        self.documents = documents

    async def mark_imported_if_complete(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> bool:
        document = await self.documents.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return False
        target_status = resolve_document_review_status(
            row.status for row in document.raw_transactions
        )
        if target_status is not UploadedDocumentStatus.IMPORTED:
            return False
        await transition_document_status(self.documents, document, target_status)
        return True

    async def sync_review_status(self, document: UploadedDocument) -> bool:
        target_status = resolve_document_review_status(
            row.status for row in document.raw_transactions
        )
        if target_status is None or document.status is target_status:
            return False
        await transition_document_status(self.documents, document, target_status)
        return True


async def transition_document_status(
    documents: "DocumentRepository",
    document: UploadedDocument,
    target_status: UploadedDocumentStatus,
) -> None:
    resolved_status = resolve_document_status_transition(
        current_status=document.status,
        target_status=target_status,
    )
    await documents.mark_document_status(document, resolved_status)
