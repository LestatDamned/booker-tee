from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.features.imports.domain.types import RawTransactionStatus


class ReviewQueueItem(Protocol):
    id: UUID
    row_index: int
    status: RawTransactionStatus


TERMINAL_REVIEW_STATUSES = frozenset(
    {
        RawTransactionStatus.CONFIRMED,
        RawTransactionStatus.IGNORED,
        RawTransactionStatus.DUPLICATE,
    }
)


@dataclass(frozen=True)
class ReviewQueueSnapshot:
    total: int
    completed: int
    remaining: int
    first_remaining_item_id: UUID | None
    ordered_item_ids: tuple[UUID, ...]


def is_review_terminal(status: RawTransactionStatus) -> bool:
    return status in TERMINAL_REVIEW_STATUSES


def is_reviewable(status: RawTransactionStatus) -> bool:
    return not is_review_terminal(status)


def review_queue_snapshot(items: Sequence[ReviewQueueItem]) -> ReviewQueueSnapshot:
    ordered_items = sorted(items, key=lambda item: (item.row_index, str(item.id)))
    completed = sum(1 for item in ordered_items if is_review_terminal(item.status))
    first_remaining_item = next(
        (item for item in ordered_items if is_reviewable(item.status)),
        None,
    )
    return ReviewQueueSnapshot(
        total=len(ordered_items),
        completed=completed,
        remaining=len(ordered_items) - completed,
        first_remaining_item_id=(
            first_remaining_item.id if first_remaining_item is not None else None
        ),
        ordered_item_ids=tuple(item.id for item in ordered_items),
    )
