from datetime import date
from decimal import Decimal
from uuid import UUID

from app.db.base import utc_now
from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.ledger.domain.money import (
    LedgerPostingPlan,
    affects_profit_for_operation_type,
)
from app.features.ledger.domain.text import clean_description
from app.features.ledger.models import (
    MoneyEntry,
    Operation,
    OperationSource,
    OperationStatus,
    OperationType,
)
from app.features.ledger.schemas.manual import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)
from app.features.properties.models import Property
from app.features.workspaces.service import WorkspaceContext


class LedgerRecordFactory:
    @staticmethod
    def build_manual_income_expense_operation(
        *,
        context: WorkspaceContext,
        command: CreateManualIncomeExpenseCommand,
        category: Category,
        property_: Property | None,
        idempotency_fingerprint: str | None,
    ) -> Operation:
        return _build_confirmed_operation(
            context=context,
            operation_type=command.operation_type,
            source=OperationSource.MANUAL,
            category_id=category.id,
            property_id=property_.id if property_ else None,
            description=clean_description(command.description),
            operation_date=command.operation_date,
            idempotency_key=str(command.idempotency_key) if command.idempotency_key else None,
            idempotency_fingerprint=idempotency_fingerprint,
        )

    @staticmethod
    def build_manual_transfer_operation(
        *,
        context: WorkspaceContext,
        command: CreateManualTransferCommand,
        transfer_category: Category,
        idempotency_fingerprint: str | None,
    ) -> Operation:
        return _build_confirmed_operation(
            context=context,
            operation_type=OperationType.TRANSFER,
            source=OperationSource.MANUAL,
            category_id=transfer_category.id,
            description=clean_description(command.description),
            operation_date=command.operation_date,
            idempotency_key=str(command.idempotency_key) if command.idempotency_key else None,
            idempotency_fingerprint=idempotency_fingerprint,
        )

    @staticmethod
    def build_imported_income_expense_operation(
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        plan: LedgerPostingPlan,
        category: Category,
        property_: Property | None,
        idempotency_key: UUID | None = None,
        idempotency_fingerprint: str | None = None,
    ) -> Operation:
        return _build_confirmed_operation(
            context=context,
            operation_type=plan.operation_type,
            source=OperationSource.BANK_PDF,
            category_id=category.id,
            property_id=property_.id if property_ else None,
            description=plan.description,
            operation_date=plan.operation_date,
            posting_date=plan.posting_date,
            idempotency_key=str(idempotency_key) if idempotency_key else None,
            idempotency_fingerprint=idempotency_fingerprint,
            extra_metadata={
                "source": "raw_transaction",
                "raw_transaction_id": str(raw_transaction_id),
                "uploaded_document_id": str(document_id),
            },
        )

    @staticmethod
    def build_imported_transfer_operation(
        *,
        context: WorkspaceContext,
        description: str | None,
        operation_date: date,
        posting_date: date | None,
        transfer_category: Category,
        extra_metadata: dict[str, object],
        idempotency_key: UUID | None = None,
        idempotency_fingerprint: str | None = None,
    ) -> Operation:
        return _build_confirmed_operation(
            context=context,
            operation_type=OperationType.TRANSFER,
            source=OperationSource.BANK_PDF,
            category_id=transfer_category.id,
            description=clean_description(description),
            operation_date=operation_date,
            posting_date=posting_date,
            idempotency_key=str(idempotency_key) if idempotency_key else None,
            idempotency_fingerprint=idempotency_fingerprint,
            extra_metadata=extra_metadata,
        )

    @staticmethod
    def build_money_entry(
        *,
        context: WorkspaceContext,
        operation: Operation,
        account: Account,
        amount: Decimal,
        entry_order: int,
        balance_after: Decimal | None = None,
        extra_metadata: dict[str, object] | None = None,
    ) -> MoneyEntry:
        return MoneyEntry(
            workspace_id=context.workspace.id,
            operation_id=operation.id,
            account=account,
            amount=amount,
            currency=account.currency,
            entry_order=entry_order,
            balance_after=balance_after,
            extra_metadata=extra_metadata,
        )


def _build_confirmed_operation(
    *,
    context: WorkspaceContext,
    operation_type: OperationType,
    source: OperationSource,
    category_id: UUID,
    description: str | None,
    operation_date: date,
    property_id: UUID | None = None,
    posting_date: date | None = None,
    idempotency_key: str | None = None,
    idempotency_fingerprint: str | None = None,
    extra_metadata: dict[str, object] | None = None,
) -> Operation:
    return Operation(
        workspace_id=context.workspace.id,
        type=operation_type,
        status=OperationStatus.CONFIRMED,
        affects_profit=affects_profit_for_operation_type(operation_type),
        category_id=category_id,
        property_id=property_id,
        description=description,
        operation_date=operation_date,
        posting_date=posting_date,
        source=source,
        created_by_user_id=context.user.id,
        updated_by_user_id=context.user.id,
        confirmed_at=utc_now(),
        idempotency_key=idempotency_key,
        idempotency_fingerprint=idempotency_fingerprint,
        extra_metadata=extra_metadata,
    )
