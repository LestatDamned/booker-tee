from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.accounts.models import Account
from app.features.accounts.repository import AccountRepository
from app.features.categories.models import Category
from app.features.categories.service import CategoryError, CategoryService
from app.features.imports.models import RawTransaction, RawTransactionStatus, UploadedDocumentStatus
from app.features.imports.repository import ImportRepository
from app.features.ledger.models import (
    MoneyEntry,
    Operation,
    OperationSource,
    OperationStatus,
    OperationType,
)
from app.features.ledger.repository import LedgerRepository
from app.features.properties.models import Property
from app.features.properties.service import PropertyError, PropertyService
from app.features.transaction_rules.service import rule_suggestion_auto_applies
from app.features.workspaces.service import WorkspaceContext


class LedgerPostingError(ValueError):
    pass


class PostableRawTransaction(Protocol):
    id: UUID
    status: RawTransactionStatus
    linked_operation_id: UUID | None
    account_id: UUID | None
    amount: Decimal | None
    currency: str | None
    operation_date: date | None
    posting_date: date | None
    description_normalized: str | None
    description_raw: str | None
    balance_after: Decimal | None
    dedupe_hash: str | None


class RawTransactionSuggestionState(Protocol):
    suggested_by_rule_id: UUID | None


class PostingAccount(Protocol):
    id: UUID
    currency: str


@dataclass(frozen=True)
class LedgerPostingPlan:
    operation_type: OperationType
    affects_profit: bool
    amount: Decimal
    currency: str
    operation_date: date
    posting_date: date | None
    description: str | None
    balance_after: Decimal | None


@dataclass(frozen=True)
class AccountLedgerDetail:
    account: Account
    balance: Decimal
    entries: list[MoneyEntry]


@dataclass(frozen=True)
class TransferAmounts:
    source_amount: Decimal
    destination_amount: Decimal


@dataclass(frozen=True)
class TransferSuggestion:
    raw_transaction: RawTransaction
    day_distance: int


POSTABLE_RAW_STATUSES = {
    RawTransactionStatus.NORMALIZED,
    RawTransactionStatus.SUGGESTED,
    RawTransactionStatus.MATCHED,
}
TRANSFER_POSTABLE_RAW_STATUSES = {
    RawTransactionStatus.NORMALIZED,
    RawTransactionStatus.SUGGESTED,
    RawTransactionStatus.MATCHED,
    RawTransactionStatus.NEEDS_REVIEW,
    RawTransactionStatus.POSSIBLE_DUPLICATE,
}


class LedgerPostingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
        self.imports = ImportRepository(session)
        self.ledger = LedgerRepository(session)

    async def post_raw_transaction(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        category_id: UUID | None = None,
        property_id: UUID | None = None,
    ) -> Operation:
        try:
            operation = await self._post_raw_transaction(
                context=context,
                document_id=document_id,
                raw_transaction_id=raw_transaction_id,
                category_id=category_id,
                property_id=property_id,
            )
            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def get_account_detail(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
    ) -> AccountLedgerDetail | None:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            return None
        entries_total = await self.ledger.get_confirmed_account_entries_total(
            workspace_id=workspace_id,
            account_id=account_id,
        )
        entries = await self.ledger.list_account_entries(
            workspace_id=workspace_id,
            account_id=account_id,
        )
        return AccountLedgerDetail(
            account=account,
            balance=(account.initial_balance + entries_total).quantize(Decimal("0.01")),
            entries=entries,
        )

    async def list_manual_operations(self, workspace_id: UUID) -> list[Operation]:
        return await self.ledger.list_manual_operations_for_workspace(workspace_id)

    async def undo_raw_transaction_posting(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
    ) -> Operation:
        raw_transaction = await self.imports.get_raw_transaction_for_workspace(
            context.workspace.id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise LedgerPostingError("Raw transaction row was not found.")
        if raw_transaction.linked_operation_id is None:
            raise LedgerPostingError("Raw transaction row is not linked to an operation.")

        operation = await self.ledger.get_operation_for_workspace(
            context.workspace.id,
            raw_transaction.linked_operation_id,
        )
        if operation is None:
            raise LedgerPostingError("Linked operation was not found.")
        if operation.source != OperationSource.BANK_PDF:
            raise LedgerPostingError("Only imported bank PDF operations can be undone here.")
        if operation.status != OperationStatus.CONFIRMED:
            raise LedgerPostingError("Only confirmed operations can be undone.")

        affected_document_ids = {
            linked_raw.uploaded_document_id for linked_raw in operation.raw_transactions
        }
        for linked_raw in operation.raw_transactions:
            linked_raw.linked_operation_id = None
            linked_raw.status = restored_raw_status_after_unlink(linked_raw)

        operation.status = OperationStatus.IGNORED
        operation.updated_by_user_id = context.user.id
        for affected_document_id in affected_document_ids:
            document = await self.imports.get_document_for_workspace(
                context.workspace.id,
                affected_document_id,
            )
            if document is not None:
                await self.imports.mark_document_status(
                    document,
                    UploadedDocumentStatus.REQUIRES_REVIEW,
                )
        await self.session.commit()
        return operation

    async def create_manual_income_expense(
        self,
        *,
        context: WorkspaceContext,
        operation_type: OperationType,
        account_id: UUID,
        amount: Decimal,
        operation_date: date,
        description: str | None,
        category_id: UUID | None,
        property_id: UUID | None,
    ) -> Operation:
        try:
            if operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
                raise LedgerPostingError("Manual operation must be income or expense.")
            account = await self._get_account(context.workspace.id, account_id)
            signed_amount = manual_income_expense_amount(operation_type, amount)
            category = await self._resolve_category(context.workspace.id, category_id)
            property_ = await self._resolve_property(context.workspace.id, property_id)
            operation = await self.ledger.create_operation(
                Operation(
                    workspace_id=context.workspace.id,
                    type=operation_type,
                    status=OperationStatus.CONFIRMED,
                    affects_profit=True,
                    category_id=category.id,
                    property_id=property_.id if property_ else None,
                    description=clean_description(description),
                    operation_date=operation_date,
                    source=OperationSource.MANUAL,
                    created_by_user_id=context.user.id,
                    updated_by_user_id=context.user.id,
                    confirmed_at=utc_now(),
                )
            )
            await self.ledger.create_money_entry(
                MoneyEntry(
                    workspace_id=context.workspace.id,
                    operation_id=operation.id,
                    account_id=account.id,
                    amount=signed_amount,
                    currency=account.currency,
                    entry_order=1,
                )
            )
            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def create_manual_transfer(
        self,
        *,
        context: WorkspaceContext,
        source_account_id: UUID,
        destination_account_id: UUID,
        amount: Decimal,
        operation_date: date,
        description: str | None,
    ) -> Operation:
        try:
            source_account = await self._get_account(context.workspace.id, source_account_id)
            destination_account = await self._get_account(
                context.workspace.id,
                destination_account_id,
            )
            amounts = build_manual_transfer_amounts(
                source_account_id=source_account.id,
                destination_account_id=destination_account.id,
                amount=amount,
            )
            ensure_same_currency(source_account, destination_account)
            transfer_category = await CategoryService(self.session).get_system(
                context.workspace.id,
                "transfer",
            )
            operation = await self.ledger.create_operation(
                Operation(
                    workspace_id=context.workspace.id,
                    type=OperationType.TRANSFER,
                    status=OperationStatus.CONFIRMED,
                    affects_profit=False,
                    category_id=transfer_category.id,
                    description=clean_description(description),
                    operation_date=operation_date,
                    source=OperationSource.MANUAL,
                    created_by_user_id=context.user.id,
                    updated_by_user_id=context.user.id,
                    confirmed_at=utc_now(),
                )
            )
            await self.ledger.create_money_entry(
                MoneyEntry(
                    workspace_id=context.workspace.id,
                    operation_id=operation.id,
                    account_id=source_account.id,
                    amount=amounts.source_amount,
                    currency=source_account.currency,
                    entry_order=1,
                )
            )
            await self.ledger.create_money_entry(
                MoneyEntry(
                    workspace_id=context.workspace.id,
                    operation_id=operation.id,
                    account_id=destination_account.id,
                    amount=amounts.destination_amount,
                    currency=destination_account.currency,
                    entry_order=2,
                )
            )
            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def update_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        operation_type: OperationType,
        account_id: UUID,
        amount: Decimal,
        operation_date: date,
        description: str | None,
        category_id: UUID | None,
        property_id: UUID | None,
        destination_account_id: UUID | None,
    ) -> Operation:
        try:
            operation = await self._get_manual_operation(context.workspace.id, operation_id)
            operation.type = operation_type
            operation.affects_profit = affects_profit_for_operation_type(operation_type)
            operation.description = clean_description(description)
            operation.operation_date = operation_date
            operation.updated_by_user_id = context.user.id

            if operation_type == OperationType.TRANSFER:
                destination_id = require_uuid(
                    destination_account_id,
                    "Destination account is required.",
                )
                source_account = await self._get_account(context.workspace.id, account_id)
                destination_account = await self._get_account(context.workspace.id, destination_id)
                ensure_same_currency(source_account, destination_account)
                transfer_category = await CategoryService(self.session).get_system(
                    context.workspace.id,
                    "transfer",
                )
                transfer_amounts = build_manual_transfer_amounts(
                    source_account_id=source_account.id,
                    destination_account_id=destination_account.id,
                    amount=amount,
                )
                operation.category_id = transfer_category.id
                operation.property_id = None
                await self._replace_money_entries(
                    operation,
                    [
                        MoneyEntry(
                            workspace_id=context.workspace.id,
                            operation_id=operation.id,
                            account_id=source_account.id,
                            amount=transfer_amounts.source_amount,
                            currency=source_account.currency,
                            entry_order=1,
                        ),
                        MoneyEntry(
                            workspace_id=context.workspace.id,
                            operation_id=operation.id,
                            account_id=destination_account.id,
                            amount=transfer_amounts.destination_amount,
                            currency=destination_account.currency,
                            entry_order=2,
                        ),
                    ],
                )
            else:
                if operation_type not in {OperationType.INCOME, OperationType.EXPENSE}:
                    raise LedgerPostingError(
                        "Manual operation must be income, expense, or transfer."
                    )
                account = await self._get_account(context.workspace.id, account_id)
                category = await self._resolve_category(context.workspace.id, category_id)
                property_ = await self._resolve_property(context.workspace.id, property_id)
                operation.category_id = category.id
                operation.property_id = property_.id if property_ else None
                await self._replace_money_entries(
                    operation,
                    [
                        MoneyEntry(
                            workspace_id=context.workspace.id,
                            operation_id=operation.id,
                            account_id=account.id,
                            amount=manual_income_expense_amount(operation_type, amount),
                            currency=account.currency,
                            entry_order=1,
                        )
                    ],
                )

            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def cancel_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> Operation:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        if operation.status != OperationStatus.CONFIRMED:
            raise LedgerPostingError("Only confirmed manual operations can be cancelled.")
        operation.status = OperationStatus.IGNORED
        operation.updated_by_user_id = context.user.id
        await self.session.commit()
        return operation

    async def restore_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> Operation:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        if operation.status != OperationStatus.IGNORED:
            raise LedgerPostingError("Only cancelled manual operations can be restored.")
        operation.status = OperationStatus.CONFIRMED
        operation.updated_by_user_id = context.user.id
        await self.session.commit()
        return operation

    async def delete_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> None:
        operation = await self._get_manual_operation(context.workspace.id, operation_id)
        if operation.status not in {OperationStatus.DRAFT, OperationStatus.IGNORED}:
            raise LedgerPostingError("Cancel a manual operation before deleting it.")
        await self.ledger.delete_operation(operation)
        await self.session.commit()

    async def post_raw_transaction_as_transfer(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        counterparty_account_id: UUID | None,
        matched_raw_transaction_id: UUID | None,
    ) -> Operation:
        try:
            raw_transaction = await self.imports.get_raw_transaction_for_workspace(
                context.workspace.id,
                document_id,
                raw_transaction_id,
            )
            if raw_transaction is None:
                raise LedgerPostingError("Raw transaction row was not found.")
            ensure_raw_transaction_can_post_as_transfer(raw_transaction)
            source_account = await self._get_account_for_raw_transaction(
                context.workspace.id,
                raw_transaction,
            )
            matched_raw_transaction = await self._resolve_matched_transfer_row(
                context.workspace.id,
                raw_transaction,
                matched_raw_transaction_id,
            )
            if matched_raw_transaction is not None:
                ensure_raw_transaction_can_post_as_transfer(matched_raw_transaction)
                ensure_matched_transfer_account(matched_raw_transaction, counterparty_account_id)
                counterparty_account = await self._get_account_for_raw_transaction(
                    context.workspace.id,
                    matched_raw_transaction,
                )
                counterparty_amount = require_raw_amount(matched_raw_transaction)
            else:
                if counterparty_account_id is None:
                    raise LedgerPostingError("Transfer account is required.")
                counterparty_account = await self._get_account(
                    context.workspace.id,
                    counterparty_account_id,
                )
                ensure_distinct_accounts(source_account.id, counterparty_account.id)
                counterparty_amount = -require_raw_amount(raw_transaction)
            ensure_same_currency(source_account, counterparty_account)
            ensure_balanced_transfer(require_raw_amount(raw_transaction), counterparty_amount)
            transfer_category = await CategoryService(self.session).get_system(
                context.workspace.id,
                "transfer",
            )
            operation = await self.ledger.create_operation(
                Operation(
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
            )
            await self.ledger.create_money_entry(
                MoneyEntry(
                    workspace_id=context.workspace.id,
                    operation_id=operation.id,
                    account_id=source_account.id,
                    amount=require_raw_amount(raw_transaction),
                    currency=source_account.currency,
                    entry_order=1,
                    balance_after=raw_transaction.balance_after,
                )
            )
            await self.ledger.create_money_entry(
                MoneyEntry(
                    workspace_id=context.workspace.id,
                    operation_id=operation.id,
                    account_id=counterparty_account.id,
                    amount=counterparty_amount,
                    currency=counterparty_account.currency,
                    entry_order=2,
                    balance_after=matched_raw_transaction.balance_after
                    if matched_raw_transaction
                    else None,
                )
            )
            await self.imports.link_raw_transaction_to_operation(
                raw_transaction,
                operation_id=operation.id,
            )
            if matched_raw_transaction is not None:
                await self.imports.link_raw_transaction_to_operation(
                    matched_raw_transaction,
                    operation_id=operation.id,
                )
                await self._mark_document_imported_if_complete(
                    context.workspace.id,
                    matched_raw_transaction.uploaded_document_id,
                )
            await self._mark_document_imported_if_complete(context.workspace.id, document_id)
            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

    async def list_transfer_suggestions_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[TransferSuggestion]]:
        suggestions: dict[UUID, list[TransferSuggestion]] = {}
        for raw_transaction in raw_transactions:
            if raw_transaction.linked_operation_id is not None:
                continue
            candidates = await self.imports.list_transfer_candidate_raw_transactions(
                workspace_id=workspace_id,
                raw_transaction=raw_transaction,
            )
            if not candidates:
                continue
            suggestions[raw_transaction.id] = [
                TransferSuggestion(
                    raw_transaction=candidate,
                    day_distance=abs(
                        (candidate.operation_date - raw_transaction.operation_date).days
                    )
                    if candidate.operation_date and raw_transaction.operation_date
                    else 0,
                )
                for candidate in candidates
            ]
        return suggestions

    async def _post_raw_transaction(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        category_id: UUID | None,
        property_id: UUID | None,
    ) -> Operation:
        raw_transaction = await self.imports.get_raw_transaction_for_workspace(
            context.workspace.id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise LedgerPostingError("Raw transaction row was not found.")
        if raw_transaction.account_id is None:
            raise LedgerPostingError("Raw transaction row has no account.")

        account = await self.accounts.get_for_workspace(
            context.workspace.id,
            raw_transaction.account_id,
        )
        if account is None:
            raise LedgerPostingError("Raw transaction account is not available in this workspace.")
        if raw_transaction.dedupe_hash is not None:
            has_confirmed_duplicate = (
                await self.imports.has_confirmed_raw_transaction_with_dedupe_hash(
                    workspace_id=context.workspace.id,
                    dedupe_hash=raw_transaction.dedupe_hash,
                    exclude_raw_transaction_id=raw_transaction.id,
                )
            )
            if has_confirmed_duplicate:
                raise LedgerPostingError(
                    "A confirmed raw transaction already uses this dedupe hash."
                )

        plan = build_ledger_posting_plan(raw_transaction, account)
        try:
            suggested_category_id = (
                raw_transaction.suggested_category_id
                if rule_suggestion_auto_applies(raw_transaction)
                else None
            )
            suggested_property_id = (
                raw_transaction.suggested_property_id
                if rule_suggestion_auto_applies(raw_transaction)
                else None
            )
            category = await self._resolve_category(
                context.workspace.id,
                category_id or suggested_category_id,
            )
            property_ = await PropertyService(self.session).get_for_workspace(
                context.workspace.id,
                property_id or suggested_property_id,
            )
        except (CategoryError, PropertyError) as exc:
            raise LedgerPostingError(str(exc)) from exc
        operation = await self.ledger.create_operation(
            Operation(
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
        )
        await self.ledger.create_money_entry(
            MoneyEntry(
                workspace_id=context.workspace.id,
                operation_id=operation.id,
                account_id=account.id,
                amount=plan.amount,
                currency=plan.currency,
                entry_order=1,
                balance_after=plan.balance_after,
                extra_metadata={"source": "bank_pdf"},
            )
        )
        await self.imports.link_raw_transaction_to_operation(
            raw_transaction,
            operation_id=operation.id,
        )
        await self._mark_document_imported_if_complete(context.workspace.id, document_id)
        return operation

    async def _resolve_category(
        self,
        workspace_id: UUID,
        category_id: UUID | None,
    ) -> Category:
        category_service = CategoryService(self.session)
        if category_id is not None:
            category = await category_service.get_for_workspace(workspace_id, category_id)
            if category is None:
                raise LedgerPostingError("Category is not available in this workspace.")
            return category
        return await category_service.get_uncategorized(workspace_id)

    async def _resolve_property(
        self,
        workspace_id: UUID,
        property_id: UUID | None,
    ) -> Property | None:
        try:
            return await PropertyService(self.session).get_for_workspace(
                workspace_id,
                property_id,
            )
        except PropertyError as exc:
            raise LedgerPostingError(str(exc)) from exc

    async def _get_manual_operation(self, workspace_id: UUID, operation_id: UUID) -> Operation:
        operation = await self.ledger.get_operation_for_workspace(workspace_id, operation_id)
        if operation is None:
            raise LedgerPostingError("Manual operation was not found.")
        if operation.source != OperationSource.MANUAL:
            raise LedgerPostingError("Only manual operations can be changed here.")
        return operation

    async def _replace_money_entries(
        self,
        operation: Operation,
        money_entries: list[MoneyEntry],
    ) -> None:
        for money_entry in list(operation.money_entries):
            await self.session.delete(money_entry)
        operation.money_entries.clear()
        await self.session.flush()
        for money_entry in money_entries:
            await self.ledger.create_money_entry(money_entry)

    async def _get_account(self, workspace_id: UUID, account_id: UUID) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            raise LedgerPostingError("Account is not available in this workspace.")
        return account

    async def _get_account_for_raw_transaction(
        self,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
    ) -> Account:
        if raw_transaction.account_id is None:
            raise LedgerPostingError("Raw transaction row has no account.")
        return await self._get_account(workspace_id, raw_transaction.account_id)

    async def _resolve_matched_transfer_row(
        self,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
        matched_raw_transaction_id: UUID | None,
    ) -> RawTransaction | None:
        if matched_raw_transaction_id is None:
            return None
        matched_raw_transaction = await self.imports.get_raw_transaction_by_id_for_workspace(
            workspace_id,
            matched_raw_transaction_id,
        )
        if matched_raw_transaction is None:
            raise LedgerPostingError("Matched raw transaction row was not found.")
        candidates = await self.imports.list_transfer_candidate_raw_transactions(
            workspace_id=workspace_id,
            raw_transaction=raw_transaction,
        )
        if matched_raw_transaction.id not in {candidate.id for candidate in candidates}:
            raise LedgerPostingError("Matched raw transaction is not a transfer candidate.")
        return matched_raw_transaction

    async def _mark_document_imported_if_complete(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> None:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None or not document.raw_transactions:
            return
        complete_statuses = {
            RawTransactionStatus.CONFIRMED,
            RawTransactionStatus.IGNORED,
            RawTransactionStatus.DUPLICATE,
        }
        if all(row.status in complete_statuses for row in document.raw_transactions):
            await self.imports.mark_document_status(document, UploadedDocumentStatus.IMPORTED)


def build_ledger_posting_plan(
    raw_transaction: PostableRawTransaction,
    account: PostingAccount,
) -> LedgerPostingPlan:
    if raw_transaction.linked_operation_id is not None:
        raise LedgerPostingError("Raw transaction row is already linked to an operation.")
    if raw_transaction.status not in POSTABLE_RAW_STATUSES:
        raise LedgerPostingError(
            f"Raw transaction status cannot be posted: {raw_transaction.status}"
        )
    if raw_transaction.account_id != account.id:
        raise LedgerPostingError("Raw transaction account does not match selected account.")
    if raw_transaction.amount is None:
        raise LedgerPostingError("Raw transaction row has no normalized amount.")
    if raw_transaction.currency is None:
        raise LedgerPostingError("Raw transaction row has no normalized currency.")
    if raw_transaction.currency != account.currency:
        raise LedgerPostingError("Raw transaction currency does not match account currency.")
    if raw_transaction.operation_date is None:
        raise LedgerPostingError("Raw transaction row has no normalized operation date.")

    operation_type = operation_type_for_amount(raw_transaction.amount)
    return LedgerPostingPlan(
        operation_type=operation_type,
        affects_profit=affects_profit_for_operation_type(operation_type),
        amount=raw_transaction.amount,
        currency=raw_transaction.currency,
        operation_date=raw_transaction.operation_date,
        posting_date=raw_transaction.posting_date,
        description=raw_transaction.description_normalized or raw_transaction.description_raw,
        balance_after=raw_transaction.balance_after,
    )


def operation_type_for_amount(amount: Decimal) -> OperationType:
    if amount > Decimal("0.00"):
        return OperationType.INCOME
    if amount < Decimal("0.00"):
        return OperationType.EXPENSE
    raise LedgerPostingError("Zero amount raw transactions require manual review.")


def affects_profit_for_operation_type(operation_type: OperationType) -> bool:
    return operation_type in {OperationType.INCOME, OperationType.EXPENSE}


def manual_income_expense_amount(operation_type: OperationType, amount: Decimal) -> Decimal:
    normalized_amount = normalize_positive_money(amount)
    if operation_type == OperationType.INCOME:
        return normalized_amount
    if operation_type == OperationType.EXPENSE:
        return -normalized_amount
    raise LedgerPostingError("Manual operation must be income or expense.")


def build_manual_transfer_amounts(
    *,
    source_account_id: UUID,
    destination_account_id: UUID,
    amount: Decimal,
) -> TransferAmounts:
    ensure_distinct_accounts(source_account_id, destination_account_id)
    normalized_amount = normalize_positive_money(amount)
    return TransferAmounts(
        source_amount=-normalized_amount,
        destination_amount=normalized_amount,
    )


def ensure_distinct_accounts(source_account_id: UUID, destination_account_id: UUID) -> None:
    if source_account_id == destination_account_id:
        raise LedgerPostingError("Transfer accounts must be different.")


def ensure_matched_transfer_account(
    matched_raw_transaction: PostableRawTransaction,
    selected_account_id: UUID | None,
) -> None:
    if (
        selected_account_id is not None
        and matched_raw_transaction.account_id != selected_account_id
    ):
        raise LedgerPostingError(
            "Matched transfer row does not belong to the selected transfer account."
        )


def normalize_positive_money(amount: Decimal) -> Decimal:
    normalized_amount = amount.quantize(Decimal("0.01"))
    if normalized_amount <= Decimal("0.00"):
        raise LedgerPostingError("Amount must be positive.")
    return normalized_amount


def ensure_same_currency(first_account: PostingAccount, second_account: PostingAccount) -> None:
    if first_account.currency != second_account.currency:
        raise LedgerPostingError("Cross-currency transfers are not supported in the MVP.")


def require_uuid(value: UUID | None, message: str) -> UUID:
    if value is None:
        raise LedgerPostingError(message)
    return value


def ensure_balanced_transfer(first_amount: Decimal, second_amount: Decimal) -> None:
    if (first_amount + second_amount).quantize(Decimal("0.01")) != Decimal("0.00"):
        raise LedgerPostingError("Transfer entries must balance to zero.")


def require_raw_amount(raw_transaction: RawTransaction) -> Decimal:
    if raw_transaction.amount is None:
        raise LedgerPostingError("Raw transaction row has no normalized amount.")
    return raw_transaction.amount


def require_raw_operation_date(raw_transaction: RawTransaction) -> date:
    if raw_transaction.operation_date is None:
        raise LedgerPostingError("Raw transaction row has no normalized operation date.")
    return raw_transaction.operation_date


def ensure_raw_transaction_can_post_as_transfer(
    raw_transaction: PostableRawTransaction,
) -> None:
    if raw_transaction.linked_operation_id is not None:
        raise LedgerPostingError("Raw transaction row is already linked to an operation.")
    if raw_transaction.status not in TRANSFER_POSTABLE_RAW_STATUSES:
        raise LedgerPostingError(
            f"Raw transaction status cannot be posted as transfer: {raw_transaction.status}"
        )
    if raw_transaction.currency is None:
        raise LedgerPostingError("Raw transaction row has no normalized currency.")


def restored_raw_status_after_unlink(
    raw_transaction: RawTransactionSuggestionState,
) -> RawTransactionStatus:
    if raw_transaction.suggested_by_rule_id is not None:
        return RawTransactionStatus.SUGGESTED
    return RawTransactionStatus.NORMALIZED


def clean_description(description: str | None) -> str | None:
    if description is None:
        return None
    cleaned = " ".join(description.split())
    return cleaned or None
