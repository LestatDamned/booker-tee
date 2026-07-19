from datetime import date

from app.web.features.ledger.manual.form_presenter import ManualLedgerFormPresenter
from app.web.features.ledger.manual.forms import (
    ManualLedgerFormInput,
    ManualLedgerFormIssue,
)
from app.web.features.ledger.manual.queries import ManualLedgerReferenceData
from app.web.features.ledger.manual.view_models import ManualLedgerFormVM


class ManualLedgerCreatePresenter:
    def build_form(
        self,
        *,
        data: ManualLedgerReferenceData,
        return_to: str,
        submission: ManualLedgerFormInput | None = None,
        issues: tuple[ManualLedgerFormIssue, ...] = (),
        form_error: str | None = None,
    ) -> ManualLedgerFormVM:
        return ManualLedgerFormPresenter().build_form(
            data=data,
            values=submission
            or ManualLedgerFormInput(
                operation_type="income",
                operation_date=date.today().isoformat(),
            ),
            form_id="next-manual-operation-create-form",
            id_prefix="next-manual-operation-create",
            form_action="/_next/ledger/manual/new",
            return_to=return_to,
            issues=issues,
            form_error=form_error,
        )
