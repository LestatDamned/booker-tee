from dataclasses import dataclass

from app.features.ledger.domain.types import OperationStatus


@dataclass(frozen=True)
class ManualOperationActions:
    can_edit: bool
    can_cancel: bool
    can_restore: bool
    can_delete: bool


def manual_operation_actions(status: OperationStatus) -> ManualOperationActions:
    return ManualOperationActions(
        can_edit=status in {OperationStatus.CONFIRMED, OperationStatus.DRAFT},
        can_cancel=status == OperationStatus.CONFIRMED,
        can_restore=status == OperationStatus.IGNORED,
        can_delete=status in {OperationStatus.DRAFT, OperationStatus.IGNORED},
    )
