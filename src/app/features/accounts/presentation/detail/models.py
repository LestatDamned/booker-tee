from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.accounts.models import AccountType
from app.features.ledger.application.listing import LedgerPage
from app.features.ledger.models import OperationSource, OperationStatus, OperationType
from app.shared.ui.actions import ActionVM

AccountMovementActionVM = ActionVM


@dataclass(frozen=True)
class AccountDetailMetricVM:
    label: str
    value: str
    tone: str | None = None


@dataclass(frozen=True)
class AccountDetailAccountVM:
    id: UUID
    name: str
    type: AccountType
    type_label: str
    currency: str
    is_active: bool
    initial_balance: Decimal


@dataclass(frozen=True)
class AccountMovementBadgeVM:
    label: str
    tone: str


@dataclass(frozen=True)
class AccountMovementMetaVM:
    label: str
    tone: str | None = None


@dataclass(frozen=True)
class OperationResultVM:
    eyebrow: str
    title: str
    tone: str
    detail: str | None = None


@dataclass(frozen=True)
class AccountMovementDrawerVM:
    kind: str
    title: str
    form_action: str
    description: str
    status: OperationStatus
    category_id: UUID | None
    property_id: UUID | None
    source_url: str | None


@dataclass(frozen=True)
class AccountMovementEditPanelVM:
    drawer: AccountMovementDrawerVM


@dataclass(frozen=True)
class AccountMovementVM:
    id: str
    operation_id: UUID
    tone: str
    amount: Decimal
    amount_direction: str
    currency: str
    date_label: str
    badges: list[AccountMovementBadgeVM]
    description: str
    meta: list[AccountMovementMetaVM]
    result: OperationResultVM
    primary_action: AccountMovementActionVM | None
    secondary_actions: list[AccountMovementActionVM]
    edit_panel_id: str | None
    edit_form_url: str | None
    technical_label: str


@dataclass(frozen=True)
class AccountDetailPageVM:
    account: AccountDetailAccountVM
    balance: Decimal
    metrics: list[AccountDetailMetricVM]
    movements: list[AccountMovementVM]
    filters_active: bool
    page: LedgerPage


@dataclass(frozen=True)
class AccountDetailPresenterInput:
    can_write: bool
    filters_date_from: object | None
    filters_date_to: object | None
    filters_source: OperationSource | None
    filters_operation_type: OperationType | None
    filters_status: OperationStatus | None
    filters_category_id: UUID | None
    filters_property_id: UUID | None
    filters_search: str | None
