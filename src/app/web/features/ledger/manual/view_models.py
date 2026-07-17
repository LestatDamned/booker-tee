from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.web.ui.actions import ActionSetVM
from app.web.ui.money import MoneyValueVM, OperationTone

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
    per_page: int
    per_page_options: tuple[int, ...]
    active: bool
    reset_url: str


@dataclass(frozen=True)
class ManualLedgerMetaVM:
    label: str
    tone: BadgeTone = "neutral"


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
    is_targeted: bool
    is_inactive: bool


@dataclass(frozen=True)
class ManualLedgerPageVM:
    workspace_name: str
    total_label: str
    readonly_message: str
    rows: tuple[ManualLedgerRowVM, ...]
    filters: ManualLedgerFiltersVM
    show_pagination: bool
    page_label: str
    previous_url: str | None
    next_url: str | None
    empty_title: str
    empty_description: str
