from dataclasses import dataclass

from app.web.ui.actions import ActionSetVM
from app.web.ui.money import MoneyValueVM
from app.web.ui.request_state import FieldErrorVM, RequestStateVM


@dataclass(frozen=True)
class FoundationPreviewVM:
    expense: MoneyValueVM
    transfer: MoneyValueVM
    actions: ActionSetVM
    request_state: RequestStateVM
    request_error: RequestStateVM
    field_error: FieldErrorVM
    edit_panel_open: bool
