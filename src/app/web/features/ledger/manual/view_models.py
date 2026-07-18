from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.web.ui.actions import ActionSetVM, DisclosureActionVM
from app.web.ui.money import MoneyValueVM, OperationTone
from app.web.ui.request_state import FieldErrorVM, RequestStateVM

BadgeTone = Literal["neutral", "success", "warning", "danger"]


@dataclass(frozen=True)
class ManualLedgerFilterOptionVM:
    value: str
    label: str
    selected: bool = False


@dataclass(frozen=True)
class ManualLedgerFiltersVM:
    date_from: str
    date_to: str
    search: str
    operation_types: tuple[ManualLedgerFilterOptionVM, ...]
    statuses: tuple[ManualLedgerFilterOptionVM, ...]
    accounts: tuple[ManualLedgerFilterOptionVM, ...]
    categories: tuple[ManualLedgerFilterOptionVM, ...]
    properties: tuple[ManualLedgerFilterOptionVM, ...]
    per_page: int
    per_page_options: tuple[int, ...]
    active: bool
    reset_url: str


@dataclass(frozen=True)
class ManualLedgerMetaVM:
    label: str
    tone: BadgeTone = "neutral"


@dataclass(frozen=True)
class ManualLedgerOptionVM:
    value: str
    label: str
    selected: bool = False


@dataclass(frozen=True)
class ManualLedgerFormFieldIdsVM:
    operation_type: str
    amount: str
    operation_date: str
    account_id: str
    destination_account_id: str
    category_id: str
    property_id: str
    description: str


@dataclass(frozen=True)
class ManualLedgerFormErrorsVM:
    operation_type: FieldErrorVM | None = None
    amount: FieldErrorVM | None = None
    operation_date: FieldErrorVM | None = None
    account_id: FieldErrorVM | None = None
    destination_account_id: FieldErrorVM | None = None
    category_id: FieldErrorVM | None = None
    property_id: FieldErrorVM | None = None
    description: FieldErrorVM | None = None


@dataclass(frozen=True)
class ManualLedgerFormVM:
    form_id: str
    form_action: str
    return_to: str
    version: str
    operation_type: str
    amount: str
    operation_date: str
    description: str
    field_ids: ManualLedgerFormFieldIdsVM
    errors: ManualLedgerFormErrorsVM
    accounts: tuple[ManualLedgerOptionVM, ...]
    destination_accounts: tuple[ManualLedgerOptionVM, ...]
    categories: tuple[ManualLedgerOptionVM, ...]
    properties: tuple[ManualLedgerOptionVM, ...]
    request_state: RequestStateVM


@dataclass(frozen=True)
class ManualLedgerEditPanelVM:
    operation_id: UUID
    form: ManualLedgerFormVM


@dataclass(frozen=True)
class ManualLedgerCreateRegionVM:
    action: DisclosureActionVM
    panel_id: str
    content_id: str
    panel_open: bool
    reset_panel: bool
    panel: ManualLedgerFormVM | None


@dataclass(frozen=True)
class ManualLedgerRowVM:
    id: str
    operation_id: UUID
    description: str
    date_label: str
    money: MoneyValueVM | None
    operation_label: str
    operation_tone: OperationTone
    status_label: str
    status_tone: BadgeTone
    meta: tuple[ManualLedgerMetaVM, ...]
    actions: ActionSetVM
    request_state: RequestStateVM
    is_targeted: bool
    is_inactive: bool
    edit_panel_id: str
    edit_panel_content_id: str
    edit_panel_open: bool
    reset_edit_panel: bool
    edit_panel: ManualLedgerEditPanelVM | None


@dataclass(frozen=True)
class ManualLedgerPageVM:
    workspace_name: str
    total_label: str
    readonly_message: str
    create_region: ManualLedgerCreateRegionVM | None
    rows: tuple[ManualLedgerRowVM, ...]
    filters: ManualLedgerFiltersVM
    show_pagination: bool
    page_label: str
    previous_url: str | None
    next_url: str | None
    empty_title: str
    empty_description: str
