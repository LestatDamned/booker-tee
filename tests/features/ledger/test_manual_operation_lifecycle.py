import pytest

from app.features.ledger.domain.types import (
    ManualOperationActions,
    OperationStatus,
    manual_operation_actions,
)


@pytest.mark.parametrize(
    ("status", "can_edit", "can_cancel", "can_restore", "can_delete"),
    [
        (OperationStatus.CONFIRMED, True, True, False, False),
        (OperationStatus.DRAFT, True, False, False, True),
        (OperationStatus.IGNORED, False, False, True, True),
        (OperationStatus.NEEDS_REVIEW, False, False, False, False),
        (OperationStatus.DUPLICATE, False, False, False, False),
    ],
    ids=["confirmed", "draft", "ignored", "needs-review", "duplicate"],
)
def test_manual_operation_actions_are_the_lifecycle_source_of_truth(
    status: OperationStatus,
    can_edit: bool,
    can_cancel: bool,
    can_restore: bool,
    can_delete: bool,
) -> None:
    assert manual_operation_actions(status) == ManualOperationActions(
        can_edit=can_edit,
        can_cancel=can_cancel,
        can_restore=can_restore,
        can_delete=can_delete,
    )
