from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.ledger.application.listing import LedgerPage
from app.features.ledger.models import OperationStatus, OperationType


@dataclass(frozen=True)
class ManualOperationMetaVM:
    label: str
    tone: str | None = None


@dataclass(frozen=True)
class ManualOperationActionVM:
    label: str
    icon: str
    form_action: str
    variant: str = "secondary"
    confirm_message: str | None = None


@dataclass(frozen=True)
class ManualOperationDrawerVM:
    form_id: str
    form_action: str
    operation_type: OperationType
    operation_date: str
    amount: Decimal | None
    account_id: UUID | None
    destination_account_id: UUID | None
    category_id: UUID | None
    property_id: UUID | None
    description: str


@dataclass(frozen=True)
class ManualOperationRowVM:
    id: str
    operation_id: UUID
    tone: str
    status: OperationStatus
    operation_type: OperationType
    date_label: str
    amount: Decimal | None
    amount_direction: str
    currency: str
    description: str
    meta: list[ManualOperationMetaVM]
    is_current: bool
    is_inactive: bool
    drawer: ManualOperationDrawerVM
    lifecycle_actions: list[ManualOperationActionVM]
    danger_actions: list[ManualOperationActionVM]


@dataclass(frozen=True)
class ManualOperationsPageVM:
    total_label: str
    filters_active: bool
    rows: list[ManualOperationRowVM]
    page: LedgerPage
