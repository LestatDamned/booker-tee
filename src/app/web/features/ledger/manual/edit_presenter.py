from uuid import UUID

from app.features.ledger.mapping.dto import ManualOperationView
from app.features.ledger.models import OperationType
from app.web.features.ledger.manual.forms import (
    ManualLedgerEditSubmission,
    ManualLedgerFormIssue,
)
from app.web.features.ledger.manual.queries import (
    ManualLedgerEditData,
    ManualLedgerNamedReference,
)
from app.web.features.ledger.manual.view_models import (
    ManualLedgerEditErrorsVM,
    ManualLedgerEditFieldIdsVM,
    ManualLedgerEditPanelVM,
    ManualLedgerOptionVM,
)
from app.web.ui.request_state import FieldErrorVM, RequestStateVM


class ManualLedgerEditPresenter:
    def present(
        self,
        *,
        data: ManualLedgerEditData,
        return_to: str,
        submission: ManualLedgerEditSubmission | None = None,
        issues: tuple[ManualLedgerFormIssue, ...] = (),
        form_error: str | None = None,
    ) -> ManualLedgerEditPanelVM:
        operation = data.operation
        values = submission or self._initial_submission(operation)
        field_ids = self._field_ids(operation.id)
        issue_messages = {issue.field: issue.message for issue in issues}
        return ManualLedgerEditPanelVM(
            operation_id=operation.id,
            form_id=f"next-manual-operation-form-{operation.id}",
            form_action=f"/_next/ledger/manual/{operation.id}",
            return_to=return_to,
            operation_type=values.operation_type,
            amount=values.amount,
            operation_date=values.operation_date,
            description=values.description,
            field_ids=field_ids,
            errors=ManualLedgerEditErrorsVM(
                operation_type=self._field_error(
                    field_ids.operation_type,
                    issue_messages.get("operation_type"),
                ),
                amount=self._field_error(field_ids.amount, issue_messages.get("amount")),
                operation_date=self._field_error(
                    field_ids.operation_date,
                    issue_messages.get("operation_date"),
                ),
                account_id=self._field_error(
                    field_ids.account_id,
                    issue_messages.get("account_id"),
                ),
                destination_account_id=self._field_error(
                    field_ids.destination_account_id,
                    issue_messages.get("destination_account_id"),
                ),
                category_id=self._field_error(
                    field_ids.category_id,
                    issue_messages.get("category_id"),
                ),
                property_id=self._field_error(
                    field_ids.property_id,
                    issue_messages.get("property_id"),
                ),
                description=self._field_error(
                    field_ids.description,
                    issue_messages.get("description"),
                ),
            ),
            accounts=tuple(
                ManualLedgerOptionVM(
                    value=str(account.id),
                    label=f"{account.name} · {account.currency}",
                    selected=values.account_id == str(account.id),
                )
                for account in data.accounts
            ),
            destination_accounts=tuple(
                ManualLedgerOptionVM(
                    value=str(account.id),
                    label=f"{account.name} · {account.currency}",
                    selected=values.destination_account_id == str(account.id),
                )
                for account in data.accounts
            ),
            categories=self._named_options(data.categories, values.category_id),
            properties=self._named_options(data.properties, values.property_id),
            request_state=RequestStateVM(
                phase="error" if form_error else "idle",
                message=form_error,
            ),
        )

    def _initial_submission(
        self,
        operation: ManualOperationView,
    ) -> ManualLedgerEditSubmission:
        account_id = self._selected_account_id(operation)
        destination_account_id = (
            operation.destination_entry.account_id if operation.destination_entry else None
        )
        return ManualLedgerEditSubmission(
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

    def _field_ids(self, operation_id: UUID) -> ManualLedgerEditFieldIdsVM:
        prefix = f"next-manual-operation-{operation_id}"
        return ManualLedgerEditFieldIdsVM(
            operation_type=f"{prefix}-operation-type",
            amount=f"{prefix}-amount",
            operation_date=f"{prefix}-operation-date",
            account_id=f"{prefix}-account",
            destination_account_id=f"{prefix}-destination-account",
            category_id=f"{prefix}-category",
            property_id=f"{prefix}-property",
            description=f"{prefix}-description",
        )

    def _field_error(self, field_id: str, message: str | None) -> FieldErrorVM | None:
        if message is None:
            return None
        return FieldErrorVM(
            field_id=field_id,
            error_id=f"{field_id}-error",
            message=message,
        )

    def _named_options(
        self,
        references: tuple[ManualLedgerNamedReference, ...],
        selected_value: str,
    ) -> tuple[ManualLedgerOptionVM, ...]:
        return tuple(
            ManualLedgerOptionVM(
                value=str(reference.id),
                label=reference.name,
                selected=selected_value == str(reference.id),
            )
            for reference in references
        )
