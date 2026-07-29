from dataclasses import dataclass
from uuid import UUID, uuid4

from app.features.import_review.domain.queue import (
    is_review_terminal,
    is_reviewable,
    review_queue_snapshot,
)
from app.features.imports.statements.types import RawTransactionStatus


@dataclass(frozen=True)
class QueueItemStub:
    id: UUID
    row_index: int
    status: RawTransactionStatus


def test_review_queue_is_empty_without_rows() -> None:
    queue = review_queue_snapshot([])

    assert queue.total == 0
    assert queue.completed == 0
    assert queue.remaining == 0
    assert queue.first_remaining_item_id is None
    assert queue.ordered_item_ids == ()


def test_review_queue_orders_rows_and_finds_first_remaining() -> None:
    remaining = QueueItemStub(uuid4(), 2, RawTransactionStatus.NEEDS_REVIEW)
    completed = QueueItemStub(uuid4(), 1, RawTransactionStatus.CONFIRMED)

    queue = review_queue_snapshot([remaining, completed])

    assert queue.total == 2
    assert queue.completed == 1
    assert queue.remaining == 1
    assert queue.first_remaining_item_id == remaining.id
    assert queue.ordered_item_ids == (completed.id, remaining.id)


def test_matched_row_remains_reviewable_and_postable_in_queue() -> None:
    matched = QueueItemStub(uuid4(), 1, RawTransactionStatus.MATCHED)

    queue = review_queue_snapshot([matched])

    assert is_review_terminal(RawTransactionStatus.MATCHED) is False
    assert is_reviewable(RawTransactionStatus.MATCHED) is True
    assert queue.completed == 0
    assert queue.remaining == 1
    assert queue.first_remaining_item_id == matched.id


def test_only_confirmed_ignored_and_duplicate_rows_complete_queue() -> None:
    statuses = [
        RawTransactionStatus.CONFIRMED,
        RawTransactionStatus.IGNORED,
        RawTransactionStatus.DUPLICATE,
    ]
    items = [QueueItemStub(uuid4(), index, status) for index, status in enumerate(statuses)]

    queue = review_queue_snapshot(items)

    assert queue.completed == 3
    assert queue.remaining == 0
    assert queue.first_remaining_item_id is None
