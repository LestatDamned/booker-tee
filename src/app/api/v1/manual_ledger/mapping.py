from decimal import Decimal
from uuid import UUID

from app.api.v1.manual_ledger.schemas.requests import (
    ManualOperationCreateApiRequest,
    ManualOperationUpdateApiRequest,
    ManualTransferCreateApiRequest,
    ManualTransferUpdateApiRequest,
)
from app.api.v1.manual_ledger.schemas.responses import (
    ManualLedgerCapabilitiesApiResponse,
    ManualLedgerFilterOptionsApiResponse,
    ManualLedgerListApiResponse,
    ManualLedgerPaginationApiResponse,
    ManualOperationApiResponse,
    ManualOperationCapabilitiesApiResponse,
)
from app.features.ledger.domain.types import manual_operation_actions
from app.features.ledger.schemas.listing import LedgerPage
from app.features.ledger.schemas.manual import (
    CreateManualIncomeExpenseCommand,
    CreateManualOperationCommand,
    CreateManualTransferCommand,
    ManualLedgerReferenceOptionsDto,
    ManualOperationReadDto,
    UpdateManualIncomeExpenseCommand,
    UpdateManualOperationCommand,
    UpdateManualTransferCommand,
)

READONLY_REASON = "Ручные операции доступны только для просмотра согласно вашей роли."
STATE_READONLY_REASON = "Действия недоступны для текущего состояния операции."
PER_PAGE_OPTIONS = [25, 50, 100, 200]


class ManualOperationRequestMapper:
    @staticmethod
    def to_create_command(
        request: ManualOperationCreateApiRequest,
        *,
        idempotency_key: UUID,
    ) -> CreateManualOperationCommand:
        if isinstance(request, ManualTransferCreateApiRequest):
            return CreateManualTransferCommand(
                source_account_id=request.source_account_id,
                destination_account_id=request.destination_account_id,
                amount=request.decimal_amount,
                operation_date=request.operation_date,
                description=request.description,
                idempotency_key=idempotency_key,
            )
        return CreateManualIncomeExpenseCommand(
            operation_type=request.operation_type,
            account_id=request.account_id,
            amount=request.decimal_amount,
            operation_date=request.operation_date,
            description=request.description,
            category_id=request.category_id,
            property_id=request.property_id,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def to_update_command(
        operation_id: UUID,
        request: ManualOperationUpdateApiRequest,
    ) -> UpdateManualOperationCommand:
        if isinstance(request, ManualTransferUpdateApiRequest):
            return UpdateManualTransferCommand(
                operation_id=operation_id,
                source_account_id=request.source_account_id,
                destination_account_id=request.destination_account_id,
                amount=request.decimal_amount,
                operation_date=request.operation_date,
                description=request.description,
                expected_version=request.version,
            )
        return UpdateManualIncomeExpenseCommand(
            operation_id=operation_id,
            operation_type=request.operation_type,
            account_id=request.account_id,
            amount=request.decimal_amount,
            operation_date=request.operation_date,
            description=request.description,
            category_id=request.category_id,
            property_id=request.property_id,
            expected_version=request.version,
        )


class ManualLedgerResponseMapper:
    @staticmethod
    def list_response(
        *,
        operations: list[ManualOperationReadDto],
        page: LedgerPage,
        references: ManualLedgerReferenceOptionsDto,
        can_write: bool,
        target_operation: ManualOperationReadDto | None,
    ) -> ManualLedgerListApiResponse:
        return ManualLedgerListApiResponse(
            items=[
                ManualLedgerResponseMapper.operation_response(
                    operation,
                    can_write=can_write,
                )
                for operation in operations
            ],
            pagination=ManualLedgerPaginationApiResponse.model_validate(page),
            filter_options=ManualLedgerResponseMapper.filter_options(references),
            capabilities=ManualLedgerCapabilitiesApiResponse(
                can_create=can_write,
                readonly_reason=None if can_write else READONLY_REASON,
            ),
            target_operation_id=target_operation.id if target_operation else None,
            target_operation=(
                ManualLedgerResponseMapper.operation_response(
                    target_operation,
                    can_write=can_write,
                )
                if target_operation
                else None
            ),
        )

    @staticmethod
    def filter_options(
        references: ManualLedgerReferenceOptionsDto,
    ) -> ManualLedgerFilterOptionsApiResponse:
        return ManualLedgerFilterOptionsApiResponse.model_validate(
            {
                "accounts": references.accounts,
                "categories": references.categories,
                "properties": references.properties,
                "per_page": PER_PAGE_OPTIONS,
            }
        )

    @staticmethod
    def operation_response(
        operation: ManualOperationReadDto,
        *,
        can_write: bool,
    ) -> ManualOperationApiResponse:
        money = operation.money
        return ManualOperationApiResponse.model_validate(
            {
                "id": operation.id,
                "version": operation.version,
                "operation_type": operation.operation_type,
                "operation_date": operation.operation_date,
                "description": operation.description or "",
                "status": operation.status,
                "money": (
                    {
                        "amount": ManualLedgerResponseMapper._decimal_string(money.amount),
                        "currency": money.currency,
                    }
                    if money is not None
                    else None
                ),
                "account": operation.account,
                "source_account": operation.source_account,
                "destination_account": operation.destination_account,
                "category": operation.category,
                "property": operation.property,
                "capabilities": ManualLedgerResponseMapper._capabilities(
                    operation,
                    can_write=can_write,
                ),
            }
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
    def _decimal_string(value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), "f")
