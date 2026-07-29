from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from app.features.imports.documents.lifecycle import (
    DocumentLifecycleError,
    allowed_document_status_transitions,
    has_linked_operations,
    resolve_document_review_status,
    resolve_document_status_transition,
)
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.statements.types import RawTransactionStatus

_ALLOWED_TARGETS: Mapping[
    UploadedDocumentStatus,
    frozenset[UploadedDocumentStatus],
] = {
    UploadedDocumentStatus.UPLOADED: frozenset(
        {
            UploadedDocumentStatus.UPLOADED,
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
            UploadedDocumentStatus.PENDING_PARSE,
            UploadedDocumentStatus.PARSING,
            UploadedDocumentStatus.PARSED,
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.FAILED_TO_PARSE,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.PARSING: frozenset(
        {
            UploadedDocumentStatus.PARSING,
            UploadedDocumentStatus.PARSED,
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.FAILED_TO_PARSE,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.PARSED: frozenset(
        {
            UploadedDocumentStatus.PARSED,
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.IMPORTED,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.REQUIRES_REVIEW: frozenset(
        {
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.IMPORTED,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.FAILED_TO_PARSE: frozenset(
        {
            UploadedDocumentStatus.FAILED_TO_PARSE,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.IMPORTED: frozenset(
        {
            UploadedDocumentStatus.IMPORTED,
            UploadedDocumentStatus.REQUIRES_REVIEW,
            UploadedDocumentStatus.IGNORED,
        }
    ),
    UploadedDocumentStatus.IGNORED: frozenset(
        {
            UploadedDocumentStatus.IGNORED,
            UploadedDocumentStatus.REQUIRES_REVIEW,
        }
    ),
}


@pytest.mark.parametrize(
    ("current_status", "expected_targets"),
    _ALLOWED_TARGETS.items(),
)
def test_allowed_document_status_transition_matrix(
    current_status: UploadedDocumentStatus,
    expected_targets: frozenset[UploadedDocumentStatus],
) -> None:
    assert allowed_document_status_transitions(current_status) == expected_targets


def test_transition_rejects_reparse_of_failed_document() -> None:
    with pytest.raises(DocumentLifecycleError):
        resolve_document_status_transition(
            current_status=UploadedDocumentStatus.FAILED_TO_PARSE,
            target_status=UploadedDocumentStatus.PARSED,
        )


@pytest.mark.parametrize(
    ("row_statuses", "expected_status"),
    [
        ([], None),
        (
            [
                RawTransactionStatus.CONFIRMED,
                RawTransactionStatus.IGNORED,
                RawTransactionStatus.DUPLICATE,
            ],
            UploadedDocumentStatus.IMPORTED,
        ),
        (
            [
                RawTransactionStatus.CONFIRMED,
                RawTransactionStatus.NEEDS_REVIEW,
            ],
            UploadedDocumentStatus.REQUIRES_REVIEW,
        ),
    ],
)
def test_resolve_document_review_status(
    row_statuses: list[RawTransactionStatus],
    expected_status: UploadedDocumentStatus | None,
) -> None:
    assert resolve_document_review_status(row_statuses) is expected_status


def test_has_linked_operations_detects_linked_row() -> None:
    rows = [LinkedOperationStub()]

    assert has_linked_operations(rows) is False

    rows[0].linked_operation_id = uuid4()

    assert has_linked_operations(rows) is True


@dataclass
class LinkedOperationStub:
    linked_operation_id: UUID | None = None
