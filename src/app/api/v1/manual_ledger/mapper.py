from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.api.v1.manual_ledger.schemas.responses import (
    ManualLedgerAccountReferenceApiResponse,
    ManualLedgerCapabilitiesApiResponse,
    ManualLedgerFilterOptionsApiResponse,
    ManualLedgerListApiResponse,
    ManualLedgerMoneyApiResponse,
    ManualLedgerNamedReferenceApiResponse,
    ManualLedgerPaginationApiResponse,
    ManualOperationApiResponse,
    ManualOperationCapabilitiesApiResponse,
)
from app.features.ledger.application.listing import LedgerPage
from app.features.ledger.application.manual_contracts import ManualOperationReadDto
from app.features.ledger.application.manual_operations import (
    ManualLedgerReferenceOptionsDto,
)
from app.features.ledger.domain.types import manual_operation_actions

READONLY_REASON = "Ручные операции доступны только для просмотра согласно вашей роли."
STATE_READONLY_REASON = "Действия недоступны для текущего состояния операции."
PER_PAGE_OPTIONS = [25, 50, 100, 200]


class NamedReference(Protocol):
    id: UUID
    name: str


class ManualLedgerApiResponseMapper:
    @staticmethod
    def list_response(
        *,
        operations: list[ManualOperationReadDto],
        page: LedgerPage,
        references: ManualLedgerReferenceOptionsDto,
        can_write: bool,
        target_operation_id: UUID | None,
    ) -> ManualLedgerListApiResponse:
        return ManualLedgerListApiResponse(
            items=[
                ManualLedgerApiResponseMapper.operation_response(
                    operation,
                    can_write=can_write,
                )
                for operation in operations
            ],
            pagination=ManualLedgerPaginationApiResponse(
                page=page.page,
                per_page=page.per_page,
                total=page.total,
                total_pages=page.total_pages,
                has_previous=page.has_previous,
                has_next=page.has_next,
            ),
            filter_options=ManualLedgerApiResponseMapper.filter_options(references),
            capabilities=ManualLedgerCapabilitiesApiResponse(
                can_create=can_write,
                readonly_reason=None if can_write else READONLY_REASON,
            ),
            target_operation_id=target_operation_id,
        )

    @staticmethod
    def filter_options(
        references: ManualLedgerReferenceOptionsDto,
    ) -> ManualLedgerFilterOptionsApiResponse:
        return ManualLedgerFilterOptionsApiResponse(
            accounts=[
                ManualLedgerAccountReferenceApiResponse(
                    id=account.id,
                    name=account.name,
                    currency=account.currency,
                )
                for account in references.accounts
            ],
            categories=[
                ManualLedgerApiResponseMapper._required_named_reference(category)
                for category in references.categories
            ],
            properties=[
                ManualLedgerApiResponseMapper._required_named_reference(property_)
                for property_ in references.properties
            ],
            per_page=PER_PAGE_OPTIONS,
        )

    @staticmethod
    def operation_response(
        operation: ManualOperationReadDto,
        *,
        can_write: bool,
    ) -> ManualOperationApiResponse:
        return ManualOperationApiResponse(
            id=operation.id,
            version=operation.version,
            operation_type=operation.operation_type,
            operation_date=operation.operation_date,
            description=operation.description or "",
            status=operation.status,
            money=(
                ManualLedgerMoneyApiResponse(
                    amount=ManualLedgerApiResponseMapper._decimal_string(operation.money.amount),
                    currency=operation.money.currency,
                )
                if operation.money is not None
                else None
            ),
            account=ManualLedgerApiResponseMapper._named_reference(operation.account),
            source_account=ManualLedgerApiResponseMapper._named_reference(operation.source_account),
            destination_account=ManualLedgerApiResponseMapper._named_reference(
                operation.destination_account
            ),
            category=ManualLedgerApiResponseMapper._named_reference(operation.category),
            property=ManualLedgerApiResponseMapper._named_reference(operation.property),
            capabilities=ManualLedgerApiResponseMapper._capabilities(
                operation,
                can_write=can_write,
            ),
        )

    @staticmethod
    def _capabilities(
        operation: ManualOperationReadDto,
        *,
        can_write: bool,
    ) -> ManualOperationCapabilitiesApiResponse:
        if not can_write:
            return ManualOperationCapabilitiesApiResponse(
                can_edit=False,
                can_cancel=False,
                can_restore=False,
                can_delete=False,
                readonly_reason=READONLY_REASON,
            )
        actions = manual_operation_actions(operation.status)
        if any((actions.can_edit, actions.can_cancel, actions.can_restore, actions.can_delete)):
            return ManualOperationCapabilitiesApiResponse(
                can_edit=actions.can_edit,
                can_cancel=actions.can_cancel,
                can_restore=actions.can_restore,
                can_delete=actions.can_delete,
            )
        return ManualOperationCapabilitiesApiResponse(
            can_edit=False,
            can_cancel=False,
            can_restore=False,
            can_delete=False,
            readonly_reason=STATE_READONLY_REASON,
        )

    @staticmethod
    def _named_reference(
        reference: NamedReference | None,
    ) -> ManualLedgerNamedReferenceApiResponse | None:
        if reference is None:
            return None
        return ManualLedgerApiResponseMapper._required_named_reference(reference)

    @staticmethod
    def _required_named_reference(
        reference: NamedReference,
    ) -> ManualLedgerNamedReferenceApiResponse:
        return ManualLedgerNamedReferenceApiResponse(id=reference.id, name=reference.name)

    @staticmethod
    def _decimal_string(value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), "f")
