from decimal import Decimal
from uuid import UUID

from app.db.base import utc_now
from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.imports.models import RawTransaction
from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)
from app.features.ledger.domain.raw_transactions import (
    LedgerPostingPlan,
    require_raw_operation_date,
)
from app.features.ledger.domain.text import clean_description
from app.features.ledger.models import (
    MoneyEntry,
    Operation,
    OperationSource,
    OperationStatus,
    OperationType,
)
from app.features.properties.models import Property
from app.features.workspaces.service import WorkspaceContext


def build_manual_income_expense_operation(
    *,
    context: WorkspaceContext,
    command: CreateManualIncomeExpenseCommand,
    category: Category,
    property_: Property | None,
) -> Operation:
    return Operation(
        workspace_id=context.workspace.id,
        type=command.operation_type,
        status=OperationStatus.CONFIRMED,
        affects_profit=True,
        category_id=category.id,
        property_id=property_.id if property_ else None,
        description=clean_description(command.description),
        operation_date=command.operation_date,
        source=OperationSource.MANUAL,
        created_by_user_id=context.user.id,
        updated_by_user_id=context.user.id,
        confirmed_at=utc_now(),
    )


def build_manual_transfer_operation(
    *,
    context: WorkspaceContext,
    command: CreateManualTransferCommand,
    transfer_category: Category,
) -> Operation:
    return Operation(
        workspace_id=context.workspace.id,
        type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        affects_profit=False,
        category_id=transfer_category.id,
        description=clean_description(command.description),
        operation_date=command.operation_date,
        source=OperationSource.MANUAL,
        created_by_user_id=context.user.id,
        updated_by_user_id=context.user.id,
        confirmed_at=utc_now(),
    )


def build_bank_pdf_operation(
    *,
    context: WorkspaceContext,
    document_id: UUID,
    raw_transaction: RawTransaction,
    plan: LedgerPostingPlan,
    category: Category,
    property_: Property | None,
) -> Operation:
    return Operation(
        workspace_id=context.workspace.id,
        type=plan.operation_type,
        status=OperationStatus.CONFIRMED,
        affects_profit=plan.affects_profit,
        category_id=category.id,
        property_id=property_.id if property_ else None,
        description=plan.description,
        operation_date=plan.operation_date,
        posting_date=plan.posting_date,
        source=OperationSource.BANK_PDF,
        created_by_user_id=context.user.id,
        updated_by_user_id=context.user.id,
        confirmed_at=utc_now(),
        extra_metadata={
            "source": "raw_transaction",
            "raw_transaction_id": str(raw_transaction.id),
            "uploaded_document_id": str(document_id),
        },
    )


def build_bank_pdf_transfer_operation(
    *,
    context: WorkspaceContext,
    raw_transaction: RawTransaction,
    matched_raw_transaction: RawTransaction | None,
    transfer_category: Category,
) -> Operation:
    return Operation(
        workspace_id=context.workspace.id,
        type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        affects_profit=False,
        category_id=transfer_category.id,
        description=clean_description(
            raw_transaction.description_normalized or raw_transaction.description_raw
        ),
        operation_date=require_raw_operation_date(raw_transaction),
        posting_date=raw_transaction.posting_date,
        source=OperationSource.BANK_PDF,
        created_by_user_id=context.user.id,
        updated_by_user_id=context.user.id,
        confirmed_at=utc_now(),
        extra_metadata={
            "source": "raw_transfer",
            "raw_transaction_id": str(raw_transaction.id),
            "matched_raw_transaction_id": str(matched_raw_transaction.id)
            if matched_raw_transaction
            else None,
        },
    )


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
        account_id=account.id,
        amount=amount,
        currency=account.currency,
        entry_order=entry_order,
        balance_after=balance_after,
        extra_metadata=extra_metadata,
    )
