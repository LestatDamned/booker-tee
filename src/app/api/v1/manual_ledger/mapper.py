from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.api.v1.manual_ledger.references import ManualLedgerReferences
from app.api.v1.manual_ledger.schemas import (
    EntryDirection,
    ManualLedgerAccountReference,
    ManualLedgerCapabilities,
    ManualLedgerFilterOptions,
    ManualLedgerListResponse,
    ManualLedgerMoney,
    ManualLedgerNamedReference,
    ManualLedgerPaginationResponse,
    ManualOperationCapabilities,
    ManualOperationResponse,
)
from app.features.ledger.application.listing import LedgerPage
from app.features.ledger.mapping.dto import (
    ManualOperationView,
    OperationRefMoneyEntryView,
)
from app.features.ledger.models import OperationStatus, OperationType

READONLY_REASON = "Ручные операции доступны только для просмотра согласно вашей роли."
STATE_READONLY_REASON = "Действия недоступны для текущего состояния операции."
PER_PAGE_OPTIONS = [25, 50, 100, 200]


class NamedReference(Protocol):
    id: UUID
    name: str


def build_manual_ledger_response(
    *,
    operations: list[ManualOperationView],
    page: LedgerPage,
    references: ManualLedgerReferences,
    can_write: bool,
    target_operation_id: UUID | None,
) -> ManualLedgerListResponse:
    return ManualLedgerListResponse(
        items=[
            manual_operation_response(operation, can_write=can_write) for operation in operations
        ],
        pagination=ManualLedgerPaginationResponse(
            page=page.page,
            per_page=page.per_page,
            total=page.total,
            total_pages=page.total_pages,
            has_previous=page.has_previous,
            has_next=page.has_next,
        ),
        filter_options=manual_ledger_filter_options(references),
        capabilities=ManualLedgerCapabilities(
            can_create=can_write,
            readonly_reason=None if can_write else READONLY_REASON,
        ),
        target_operation_id=target_operation_id,
    )


def manual_ledger_filter_options(
    references: ManualLedgerReferences,
) -> ManualLedgerFilterOptions:
    return ManualLedgerFilterOptions(
        accounts=[
            ManualLedgerAccountReference(
                id=account.id,
                name=account.name,
                currency=account.currency,
            )
            for account in references.accounts
        ],
        categories=[_required_named_reference(category) for category in references.categories],
        properties=[_required_named_reference(property_) for property_ in references.properties],
        per_page=PER_PAGE_OPTIONS,
    )


def manual_operation_response(
    operation: ManualOperationView,
    *,
    can_write: bool,
) -> ManualOperationResponse:
    return ManualOperationResponse(
        id=operation.id,
        version=operation.version,
        operation_date=operation.operation_date.isoformat(),
        description=operation.description or "",
        status=operation.status,
        money=_money(operation),
        account=_account_reference(operation.primary_entry)
        if operation.type != OperationType.TRANSFER
        else None,
        source_account=_account_reference(operation.source_entry),
        destination_account=_account_reference(operation.destination_entry),
        category=_named_reference(operation.category),
        property=_named_reference(operation.property),
        capabilities=_capabilities(operation, can_write=can_write),
    )


def _money(operation: ManualOperationView) -> ManualLedgerMoney | None:
    entry = (
        operation.source_entry
        if operation.type == OperationType.TRANSFER
        else operation.primary_entry
    )
    if operation.edit_amount is None or entry is None or entry.account is None:
        return None
    return ManualLedgerMoney(
        amount=_decimal_string(operation.edit_amount),
        currency=entry.account.currency,
        operation_type=operation.type,
        entry_direction=_entry_direction(operation.type),
    )


def _entry_direction(operation_type: OperationType) -> EntryDirection:
    if operation_type == OperationType.INCOME:
        return "inflow"
    if operation_type == OperationType.EXPENSE:
        return "outflow"
    return "transfer"


def _capabilities(
    operation: ManualOperationView,
    *,
    can_write: bool,
) -> ManualOperationCapabilities:
    if not can_write:
        return ManualOperationCapabilities(
            can_edit=False,
            can_cancel=False,
            can_restore=False,
            can_delete=False,
            readonly_reason=READONLY_REASON,
        )
    if operation.status == OperationStatus.CONFIRMED:
        return ManualOperationCapabilities(
            can_edit=True,
            can_cancel=True,
            can_restore=False,
            can_delete=False,
        )
    if operation.status == OperationStatus.IGNORED:
        return ManualOperationCapabilities(
            can_edit=False,
            can_cancel=False,
            can_restore=True,
            can_delete=True,
        )
    if operation.status == OperationStatus.DRAFT:
        return ManualOperationCapabilities(
            can_edit=True,
            can_cancel=False,
            can_restore=False,
            can_delete=True,
        )
    return ManualOperationCapabilities(
        can_edit=False,
        can_cancel=False,
        can_restore=False,
        can_delete=False,
        readonly_reason=STATE_READONLY_REASON,
    )


def _account_reference(
    entry: OperationRefMoneyEntryView | None,
) -> ManualLedgerNamedReference | None:
    return _named_reference(entry.account if entry is not None else None)


def _named_reference(reference: NamedReference | None) -> ManualLedgerNamedReference | None:
    if reference is None:
        return None
    return _required_named_reference(reference)


def _required_named_reference(reference: NamedReference) -> ManualLedgerNamedReference:
    return ManualLedgerNamedReference(id=reference.id, name=reference.name)


def _decimal_string(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")
