from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from import_test_support import ImportTestSession

from app.features.import_review.application.lifecycle import (
    ImportReviewLifecycleActor,
    ImportReviewLifecycleService,
)
from app.features.import_review.domain.lifecycle import (
    ImportReviewLifecycleAction,
    import_review_lifecycle_snapshot,
    resolve_import_review_lifecycle_transition,
    restored_review_status_after_unlink,
)
from app.features.import_review.errors import (
    ImportReviewLifecycleConflictError,
    ImportReviewLifecycleError,
)
from app.features.import_review.schemas.commands import ImportReviewLifecycleCommand
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.statements.types import RawTransactionStatus


@pytest.mark.parametrize(
    ("status", "actions"),
    [
        (
            RawTransactionStatus.POSSIBLE_DUPLICATE,
            {
                ImportReviewLifecycleAction.MARK_UNIQUE,
                ImportReviewLifecycleAction.MARK_DUPLICATE,
                ImportReviewLifecycleAction.NEEDS_REVIEW,
                ImportReviewLifecycleAction.IGNORE,
            },
        ),
        (
            RawTransactionStatus.MATCHED,
            {
                ImportReviewLifecycleAction.MARK_DUPLICATE,
                ImportReviewLifecycleAction.NEEDS_REVIEW,
                ImportReviewLifecycleAction.IGNORE,
            },
        ),
        (RawTransactionStatus.IGNORED, {ImportReviewLifecycleAction.NEEDS_REVIEW}),
        (RawTransactionStatus.CONFIRMED, set()),
        (RawTransactionStatus.FAILED, set()),
    ],
)
def test_lifecycle_snapshot_exposes_only_server_allowed_actions(
    status: RawTransactionStatus,
    actions: set[ImportReviewLifecycleAction],
) -> None:
    snapshot = import_review_lifecycle_snapshot(
        status=status,
        linked_operation_id=None,
    )

    assert set(snapshot.allowed_actions) == actions


def test_linked_row_never_exposes_or_accepts_lifecycle_actions() -> None:
    snapshot = import_review_lifecycle_snapshot(
        status=RawTransactionStatus.MATCHED,
        linked_operation_id=uuid4(),
    )

    assert snapshot.allowed_actions == ()
    with pytest.raises(ImportReviewLifecycleConflictError, match="Linked"):
        resolve_import_review_lifecycle_transition(
            status=RawTransactionStatus.MATCHED,
            linked_operation_id=uuid4(),
            action=ImportReviewLifecycleAction.IGNORE,
            expected_status=RawTransactionStatus.MATCHED,
        )


def test_mark_unique_keeps_possible_duplicate_reviewable_and_replays_safely() -> None:
    transition = resolve_import_review_lifecycle_transition(
        status=RawTransactionStatus.POSSIBLE_DUPLICATE,
        linked_operation_id=None,
        action=ImportReviewLifecycleAction.MARK_UNIQUE,
        expected_status=RawTransactionStatus.POSSIBLE_DUPLICATE,
    )
    replay = resolve_import_review_lifecycle_transition(
        status=RawTransactionStatus.MATCHED,
        linked_operation_id=None,
        action=ImportReviewLifecycleAction.MARK_UNIQUE,
        expected_status=RawTransactionStatus.POSSIBLE_DUPLICATE,
    )

    assert transition.target_status is RawTransactionStatus.MATCHED
    assert transition.replayed is False
    assert replay.replayed is True


@pytest.mark.parametrize(
    "terminal_status",
    [RawTransactionStatus.CONFIRMED, RawTransactionStatus.FAILED],
)
def test_stale_and_forged_transitions_are_distinct(
    terminal_status: RawTransactionStatus,
) -> None:
    with pytest.raises(ImportReviewLifecycleConflictError, match="has changed"):
        resolve_import_review_lifecycle_transition(
            status=RawTransactionStatus.MATCHED,
            linked_operation_id=None,
            action=ImportReviewLifecycleAction.IGNORE,
            expected_status=RawTransactionStatus.POSSIBLE_DUPLICATE,
        )
    with pytest.raises(ImportReviewLifecycleError, match="not allowed"):
        resolve_import_review_lifecycle_transition(
            status=terminal_status,
            linked_operation_id=None,
            action=ImportReviewLifecycleAction.IGNORE,
            expected_status=terminal_status,
        )


def test_restored_review_status_after_unlink_preserves_rule_suggestion() -> None:
    assert (
        restored_review_status_after_unlink(SimpleNamespace(suggested_by_rule_id=uuid4()))
        is RawTransactionStatus.SUGGESTED
    )
    assert (
        restored_review_status_after_unlink(SimpleNamespace(suggested_by_rule_id=None))
        is RawTransactionStatus.NORMALIZED
    )


class ImportRepositoryStub:
    def __init__(self, row: object, document: object) -> None:
        self.row = row
        self.document = document

    async def get_raw_transaction_for_workspace(self, *args: object) -> object:
        return self.row

    async def mark_raw_transaction_status(
        self,
        row: object,
        status: RawTransactionStatus,
    ) -> None:
        cast(Any, row).status = status

    async def get_document_for_workspace_for_update(self, *args: object) -> object:
        return self.document

    async def mark_document_status(
        self,
        document: object,
        status: UploadedDocumentStatus,
    ) -> None:
        cast(Any, document).status = status


async def test_lifecycle_service_syncs_queue_document_and_reopens_import() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    row = lifecycle_row(document_id, RawTransactionStatus.NEEDS_REVIEW)
    confirmed = lifecycle_row(document_id, RawTransactionStatus.CONFIRMED)
    document = SimpleNamespace(
        id=document_id,
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        parse_attempts=[],
        raw_transactions=[confirmed, row],
    )
    session = ImportTestSession()
    actor = ImportReviewLifecycleActor(cast(Any, session))
    imports = ImportRepositoryStub(row, document)
    actor._documents = cast(Any, imports)
    actor._review_repository = cast(Any, imports)
    service = ImportReviewLifecycleService(cast(Any, session), actor)

    ignored = await service.execute(
        workspace_id=workspace_id,
        command=ImportReviewLifecycleCommand(
            document_id=document_id,
            item_id=row.id,
            action=ImportReviewLifecycleAction.IGNORE,
            expected_status=RawTransactionStatus.NEEDS_REVIEW,
        ),
    )

    assert ignored.replayed is False
    assert row.status is RawTransactionStatus.IGNORED
    assert document.status is UploadedDocumentStatus.IMPORTED

    restored = await service.execute(
        workspace_id=workspace_id,
        command=ImportReviewLifecycleCommand(
            document_id=document_id,
            item_id=row.id,
            action=ImportReviewLifecycleAction.NEEDS_REVIEW,
            expected_status=RawTransactionStatus.IGNORED,
        ),
    )

    assert restored.replayed is False
    assert row.status is RawTransactionStatus.NEEDS_REVIEW
    assert document.status is UploadedDocumentStatus.REQUIRES_REVIEW
    assert session.commits == 2


def lifecycle_row(document_id: UUID, status: RawTransactionStatus) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        uploaded_document_id=document_id,
        status=status,
        linked_operation_id=None,
    )
