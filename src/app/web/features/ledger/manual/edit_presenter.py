from uuid import UUID

from app.features.ledger.mapping.dto import ManualOperationView
from app.features.ledger.models import OperationType
from app.web.features.ledger.manual.form_presenter import ManualLedgerFormPresenter
from app.web.features.ledger.manual.forms import (
    ManualLedgerFormIssue,
    ManualLedgerFormSubmission,
)
from app.web.features.ledger.manual.queries import ManualLedgerEditData
from app.web.features.ledger.manual.view_models import ManualLedgerEditPanelVM


class ManualLedgerEditPresenter:
    def present(
        self,
        *,
        data: ManualLedgerEditData,
        return_to: str,
        submission: ManualLedgerFormSubmission | None = None,
        issues: tuple[ManualLedgerFormIssue, ...] = (),
        form_error: str | None = None,
    ) -> ManualLedgerEditPanelVM:
        operation = data.operation
        return ManualLedgerEditPanelVM(
            operation_id=operation.id,
            form=ManualLedgerFormPresenter().present(
                data=data.form,
                values=submission or self._initial_submission(operation),
                form_id=f"next-manual-operation-form-{operation.id}",
                id_prefix=f"next-manual-operation-{operation.id}",
                form_action=f"/_next/ledger/manual/{operation.id}",
                return_to=return_to,
                issues=issues,
                form_error=form_error,
            ),
        )

    def _initial_submission(
        self,
        operation: ManualOperationView,
    ) -> ManualLedgerFormSubmission:
        account_id = self._selected_account_id(operation)
        destination_account_id = (
            operation.destination_entry.account_id if operation.destination_entry else None
        )
        return ManualLedgerFormSubmission(
            operation_type=operation.type.value,
            account_id=str(account_id) if account_id else "",
            destination_account_id=(str(destination_account_id) if destination_account_id else ""),
            amount=str(operation.edit_amount) if operation.edit_amount is not None else "",
            operation_date=operation.operation_date.isoformat(),
            category_id=str(operation.category_id) if operation.category_id else "",
            property_id=str(operation.property_id) if operation.property_id else "",
            description=operation.description or "",
        )

    def _selected_account_id(self, operation: ManualOperationView) -> UUID | None:
        if operation.type == OperationType.TRANSFER:
            return operation.source_entry.account_id if operation.source_entry else None
        return operation.primary_entry.account_id if operation.primary_entry else None
