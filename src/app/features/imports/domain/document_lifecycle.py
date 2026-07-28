from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from app.features.imports.domain.types import (
    RawTransactionStatus,
    UploadedDocumentStatus,
)

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
