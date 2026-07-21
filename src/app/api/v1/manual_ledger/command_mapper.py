from uuid import UUID

from app.api.v1.manual_ledger.schemas.requests import (
    ManualOperationCreateApiRequest,
    ManualOperationUpdateApiRequest,
    ManualTransferCreateApiRequest,
    ManualTransferUpdateApiRequest,
)
from app.features.ledger.application.manual_contracts import (
    CreateManualIncomeExpenseCommand,
    CreateManualOperationCommand,
    CreateManualTransferCommand,
    UpdateManualIncomeExpenseCommand,
    UpdateManualOperationCommand,
    UpdateManualTransferCommand,
)


class ManualLedgerApiCommandMapper:
    @staticmethod
    def create(
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
    def update(
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
