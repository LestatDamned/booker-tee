from app.web.features.ledger.manual.forms import (
    ManualLedgerFormInput,
    ManualLedgerFormIssue,
)
from app.web.features.ledger.manual.queries import (
    ManualLedgerNamedReference,
    ManualLedgerReferenceData,
)
from app.web.features.ledger.manual.view_models import (
    ManualLedgerFormErrorsVM,
    ManualLedgerFormFieldIdsVM,
    ManualLedgerFormVM,
    ManualLedgerOptionVM,
)
from app.web.ui.actions import ActionVM
from app.web.ui.request_state import FieldErrorVM, RequestStateVM


class ManualLedgerFormPresenter:
    def build_form(
        self,
        *,
        data: ManualLedgerReferenceData,
        values: ManualLedgerFormInput,
        form_id: str,
        id_prefix: str,
        form_action: str,
        return_to: str,
        issues: tuple[ManualLedgerFormIssue, ...] = (),
        form_error: str | None = None,
        retry_action: ActionVM | None = None,
    ) -> ManualLedgerFormVM:
        field_ids = self._field_ids(id_prefix)
        issue_messages = {issue.field: issue.message for issue in issues}
        return ManualLedgerFormVM(
            form_id=form_id,
            form_action=form_action,
            return_to=return_to,
            version=values.version,
            operation_type=values.operation_type,
            amount=values.amount,
            operation_date=values.operation_date,
            description=values.description,
            field_ids=field_ids,
            errors=ManualLedgerFormErrorsVM(
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
                phase="error" if form_error or issue_messages.get("form") else "idle",
                message=form_error or issue_messages.get("form"),
                retry_action=retry_action,
            ),
        )

    def _field_ids(self, prefix: str) -> ManualLedgerFormFieldIdsVM:
        return ManualLedgerFormFieldIdsVM(
            operation_type=f"{prefix}-operation-type",
            amount=f"{prefix}-amount",
            operation_date=f"{prefix}-date",
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
