import hashlib
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.db.base import utc_now
from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.imports.models import RawTransaction
from app.features.ledger.application.manual_contracts import (
    AccountReferenceReadDto,
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    ManualOperationMoneyReadDto,
    ManualOperationReadDto,
    NamedReferenceReadDto,
)
from app.features.ledger.domain.money import affects_profit_for_operation_type
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


def manual_income_expense_fingerprint(command: CreateManualIncomeExpenseCommand) -> str:
    return _fingerprint(
        {
            "operation_type": command.operation_type.value,
            "account_id": str(command.account_id),
            "amount": _canonical_decimal(command.amount),
            "operation_date": command.operation_date.isoformat(),
            "description": command.description,
            "category_id": str(command.category_id) if command.category_id else None,
            "property_id": str(command.property_id) if command.property_id else None,
        }
    )


def manual_transfer_fingerprint(command: CreateManualTransferCommand) -> str:
    return _fingerprint(
        {
            "operation_type": OperationType.TRANSFER.value,
            "source_account_id": str(command.source_account_id),
            "destination_account_id": str(command.destination_account_id),
            "amount": _canonical_decimal(command.amount),
            "operation_date": command.operation_date.isoformat(),
            "description": command.description,
        }
    )


def _fingerprint(payload: dict[str, str | None]) -> str:
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def build_manual_income_expense_operation(
    *,
    context: WorkspaceContext,
    command: CreateManualIncomeExpenseCommand,
    category: Category,
    property_: Property | None,
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
        idempotency_fingerprint=(
            manual_income_expense_fingerprint(command) if command.idempotency_key else None
        ),
    )


def build_manual_transfer_operation(
    *,
    context: WorkspaceContext,
    command: CreateManualTransferCommand,
    transfer_category: Category,
) -> Operation:
    return _build_confirmed_operation(
        context=context,
        operation_type=OperationType.TRANSFER,
        source=OperationSource.MANUAL,
        category_id=transfer_category.id,
        description=clean_description(command.description),
        operation_date=command.operation_date,
        idempotency_key=str(command.idempotency_key) if command.idempotency_key else None,
        idempotency_fingerprint=(
            manual_transfer_fingerprint(command) if command.idempotency_key else None
        ),
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
    return _build_confirmed_operation(
        context=context,
        operation_type=plan.operation_type,
        source=OperationSource.BANK_PDF,
        category_id=category.id,
        property_id=property_.id if property_ else None,
        description=plan.description,
        operation_date=plan.operation_date,
        posting_date=plan.posting_date,
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
    idempotency_key: UUID | None = None,
    idempotency_fingerprint: str | None = None,
) -> Operation:
    return _build_confirmed_operation(
        context=context,
        operation_type=OperationType.TRANSFER,
        source=OperationSource.BANK_PDF,
        category_id=transfer_category.id,
        description=clean_description(
            raw_transaction.description_normalized or raw_transaction.description_raw
        ),
        operation_date=require_raw_operation_date(raw_transaction),
        posting_date=raw_transaction.posting_date,
        idempotency_key=str(idempotency_key) if idempotency_key else None,
        idempotency_fingerprint=idempotency_fingerprint,
        extra_metadata={
            "source": "raw_transfer",
            "raw_transaction_id": str(raw_transaction.id),
            "matched_raw_transaction_id": str(matched_raw_transaction.id)
            if matched_raw_transaction
            else None,
            "matched_uploaded_document_id": (
                str(matched_raw_transaction.uploaded_document_id)
                if matched_raw_transaction
                else None
            ),
        },
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


class ManualOperationReadDtoMapper:
    @staticmethod
    def from_model(operation: Operation) -> ManualOperationReadDto:
        primary_entry = operation.money_entries[0] if operation.money_entries else None
        source_entry = next((entry for entry in operation.money_entries if entry.amount < 0), None)
        destination_entry = next(
            (entry for entry in operation.money_entries if entry.amount > 0),
            None,
        )
        money_entry = source_entry if operation.type == OperationType.TRANSFER else primary_entry
        return ManualOperationReadDto(
            id=operation.id,
            version=operation.version,
            operation_type=operation.type,
            status=operation.status,
            operation_date=operation.operation_date,
            description=operation.description,
            money=ManualOperationReadDtoMapper._money(money_entry),
            account=(
                ManualOperationReadDtoMapper._account(primary_entry.account)
                if primary_entry is not None and operation.type != OperationType.TRANSFER
                else None
            ),
            source_account=(
                ManualOperationReadDtoMapper._account(source_entry.account)
                if source_entry is not None
                else None
            ),
            destination_account=(
                ManualOperationReadDtoMapper._account(destination_entry.account)
                if destination_entry is not None
                else None
            ),
            category=ManualOperationReadDtoMapper._named_reference(operation.category),
            property=ManualOperationReadDtoMapper._named_reference(operation.property),
        )

    @staticmethod
    def _money(entry: MoneyEntry | None) -> ManualOperationMoneyReadDto | None:
        if entry is None:
            return None
        return ManualOperationMoneyReadDto(
            amount=abs(entry.amount),
            currency=entry.currency,
        )

    @staticmethod
    def _account(account: Account | None) -> AccountReferenceReadDto | None:
        if account is None:
            return None
        return AccountReferenceReadDto(
            id=account.id,
            name=account.name,
            currency=account.currency,
        )

    @staticmethod
    def _named_reference(
        reference: Category | Property | None,
    ) -> NamedReferenceReadDto | None:
        if reference is None:
            return None
        return NamedReferenceReadDto(id=reference.id, name=reference.name)
