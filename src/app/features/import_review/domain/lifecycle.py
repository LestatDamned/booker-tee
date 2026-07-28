"""Lifecycle policy for imported transaction review."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.features.imports.domain.types import RawTransactionStatus


class ImportReviewLifecycleAction(StrEnum):
    MARK_UNIQUE = "mark_unique"
    MARK_DUPLICATE = "mark_duplicate"
    IGNORE = "ignore"
    NEEDS_REVIEW = "needs_review"


class ImportReviewLifecycleError(ValueError):
    pass


class ImportReviewLifecycleConflictError(ImportReviewLifecycleError):
    pass


@dataclass(frozen=True)
class ImportReviewLifecycleSnapshot:
    allowed_actions: tuple[ImportReviewLifecycleAction, ...]


@dataclass(frozen=True)
class ImportReviewLifecycleTransition:
    target_status: RawTransactionStatus
    replayed: bool


class ImportReviewSuggestionState(Protocol):
    suggested_by_rule_id: UUID | None


_TARGET_STATUS = {
    ImportReviewLifecycleAction.MARK_UNIQUE: RawTransactionStatus.MATCHED,
    ImportReviewLifecycleAction.MARK_DUPLICATE: RawTransactionStatus.DUPLICATE,
    ImportReviewLifecycleAction.IGNORE: RawTransactionStatus.IGNORED,
    ImportReviewLifecycleAction.NEEDS_REVIEW: RawTransactionStatus.NEEDS_REVIEW,
}

_ALLOWED_ACTIONS = {
    RawTransactionStatus.NORMALIZED: (
        ImportReviewLifecycleAction.NEEDS_REVIEW,
        ImportReviewLifecycleAction.IGNORE,
    ),
    RawTransactionStatus.SUGGESTED: (
        ImportReviewLifecycleAction.NEEDS_REVIEW,
        ImportReviewLifecycleAction.IGNORE,
    ),
    RawTransactionStatus.NEEDS_REVIEW: (ImportReviewLifecycleAction.IGNORE,),
    RawTransactionStatus.MATCHED: (
        ImportReviewLifecycleAction.MARK_DUPLICATE,
        ImportReviewLifecycleAction.NEEDS_REVIEW,
        ImportReviewLifecycleAction.IGNORE,
    ),
    RawTransactionStatus.POSSIBLE_DUPLICATE: (
        ImportReviewLifecycleAction.MARK_UNIQUE,
        ImportReviewLifecycleAction.MARK_DUPLICATE,
        ImportReviewLifecycleAction.NEEDS_REVIEW,
        ImportReviewLifecycleAction.IGNORE,
    ),
    RawTransactionStatus.IGNORED: (ImportReviewLifecycleAction.NEEDS_REVIEW,),
    RawTransactionStatus.DUPLICATE: (
        ImportReviewLifecycleAction.MARK_UNIQUE,
        ImportReviewLifecycleAction.NEEDS_REVIEW,
        ImportReviewLifecycleAction.IGNORE,
    ),
}


def import_review_lifecycle_snapshot(
    *,
    status: RawTransactionStatus,
    linked_operation_id: UUID | None,
) -> ImportReviewLifecycleSnapshot:
    if linked_operation_id is not None:
        return ImportReviewLifecycleSnapshot(allowed_actions=())
    return ImportReviewLifecycleSnapshot(allowed_actions=_ALLOWED_ACTIONS.get(status, ()))


def resolve_import_review_lifecycle_transition(
    *,
    status: RawTransactionStatus,
    linked_operation_id: UUID | None,
    action: ImportReviewLifecycleAction,
    expected_status: RawTransactionStatus,
) -> ImportReviewLifecycleTransition:
    if linked_operation_id is not None:
        raise ImportReviewLifecycleConflictError(
            "Linked raw transaction lifecycle cannot be changed."
        )
    target_status = _TARGET_STATUS[action]
    if status is target_status:
        return ImportReviewLifecycleTransition(target_status=target_status, replayed=True)
    if status is not expected_status:
        raise ImportReviewLifecycleConflictError("Raw transaction status has changed.")
    snapshot = import_review_lifecycle_snapshot(
        status=status,
        linked_operation_id=linked_operation_id,
    )
    if action not in snapshot.allowed_actions:
        raise ImportReviewLifecycleError(
            f"Action {action.value} is not allowed from status {status.value}."
        )
    return ImportReviewLifecycleTransition(target_status=target_status, replayed=False)


def restored_review_status_after_unlink(
    raw_transaction: ImportReviewSuggestionState,
) -> RawTransactionStatus:
    if raw_transaction.suggested_by_rule_id is not None:
        return RawTransactionStatus.SUGGESTED
    return RawTransactionStatus.NORMALIZED
