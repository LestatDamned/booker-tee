import pytest

from app.features.ledger.domain.types import (
    ManualOperationActions,
    OperationStatus,
    manual_operation_actions,
)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            OperationStatus.CONFIRMED,
            ManualOperationActions(
                can_edit=True,
                can_cancel=True,
                can_restore=False,
                can_delete=False,
            ),
        ),
        (
            OperationStatus.DRAFT,
            ManualOperationActions(
                can_edit=True,
                can_cancel=False,
                can_restore=False,
                can_delete=True,
            ),
        ),
        (
            OperationStatus.IGNORED,
            ManualOperationActions(
                can_edit=False,
                can_cancel=False,
                can_restore=True,
                can_delete=True,
            ),
        ),
        (
            OperationStatus.NEEDS_REVIEW,
            ManualOperationActions(
                can_edit=False,
                can_cancel=False,
                can_restore=False,
                can_delete=False,
            ),
        ),
        (
            OperationStatus.DUPLICATE,
            ManualOperationActions(
                can_edit=False,
                can_cancel=False,
                can_restore=False,
                can_delete=False,
            ),
        ),
    ],
)
def test_manual_operation_actions_are_the_lifecycle_source_of_truth(
    status: OperationStatus,
    expected: ManualOperationActions,
) -> None:
    assert manual_operation_actions(status) == expected
