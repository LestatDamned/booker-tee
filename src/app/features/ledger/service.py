from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.repository import AccountRepository
from app.features.imports.models import RawTransaction
from app.features.ledger.application.commands import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.application.imported_operation_undo import ImportedOperationUndoUseCase
from app.features.ledger.application.manual_operations import ManualOperationUseCase
from app.features.ledger.application.raw_transaction_posting import RawTransactionPostingUseCase
from app.features.ledger.application.transfer_suggestions import (
    TransferSuggestion,
    TransferSuggestionUseCase,
)
from app.features.ledger.domain import (
    affects_profit_for_operation_type,
    build_ledger_posting_plan,
    build_manual_transfer_amounts,
    ensure_balanced_transfer,
    ensure_matched_transfer_account,
    ensure_raw_transaction_can_post_as_transfer,
    manual_income_expense_amount,
    operation_type_for_amount,
    restored_raw_status_after_unlink,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.mapping.dto import (
    AccountLedgerDetailView,
    LedgerViewMapper,
    ManualOperationView,
)
from app.features.ledger.models import Operation
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext

__all__ = [
    "AccountLedgerDetail",
    "CreateManualIncomeExpenseCommand",
    "CreateManualTransferCommand",
    "LedgerPostingError",
    "LedgerPostingService",
    "TransferSuggestion",
    "UpdateManualOperationCommand",
    "affects_profit_for_operation_type",
    "build_ledger_posting_plan",
    "build_manual_transfer_amounts",
    "ensure_balanced_transfer",
    "ensure_matched_transfer_account",
    "ensure_raw_transaction_can_post_as_transfer",
    "manual_income_expense_amount",
    "operation_type_for_amount",
    "restored_raw_status_after_unlink",
]

AccountLedgerDetail = AccountLedgerDetailView


class LedgerPostingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
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
        return await RawTransactionPostingUseCase(self.session).post_raw_transaction(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            category_id=category_id,
            property_id=property_id,
        )

    async def get_account_detail(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
    ) -> AccountLedgerDetailView | None:
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
        return LedgerViewMapper.account_detail_from_parts(
            account=account,
            balance=(account.initial_balance + entries_total).quantize(Decimal("0.01")),
            entries=entries,
        )

    async def list_manual_operations(self, workspace_id: UUID) -> list[ManualOperationView]:
        operations = await self.ledger.list_manual_operations_for_workspace(workspace_id)
        return [LedgerViewMapper.manual_operation_from_model(operation) for operation in operations]

    async def undo_raw_transaction_posting(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
    ) -> Operation:
        return await ImportedOperationUndoUseCase(self.session).undo_raw_transaction_posting(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
        )

    async def create_manual_income_expense(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualIncomeExpenseCommand,
    ) -> Operation:
        return await ManualOperationUseCase(self.session).create_income_expense(
            context=context,
            command=command,
        )

    async def create_manual_transfer(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualTransferCommand,
    ) -> Operation:
        return await ManualOperationUseCase(self.session).create_transfer(
            context=context,
            command=command,
        )

    async def update_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateManualOperationCommand,
    ) -> Operation:
        return await ManualOperationUseCase(self.session).update(
            context=context,
            command=command,
        )

    async def cancel_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> Operation:
        return await ManualOperationUseCase(self.session).cancel(
            context=context,
            operation_id=operation_id,
        )

    async def restore_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> Operation:
        return await ManualOperationUseCase(self.session).restore(
            context=context,
            operation_id=operation_id,
        )

    async def delete_manual_operation(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
    ) -> None:
        await ManualOperationUseCase(self.session).delete(
            context=context,
            operation_id=operation_id,
        )

    async def post_raw_transaction_as_transfer(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        counterparty_account_id: UUID | None,
        matched_raw_transaction_id: UUID | None,
    ) -> Operation:
        return await RawTransactionPostingUseCase(
            self.session,
        ).post_raw_transaction_as_transfer(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            counterparty_account_id=counterparty_account_id,
            matched_raw_transaction_id=matched_raw_transaction_id,
        )

    async def list_transfer_suggestions_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[TransferSuggestion]]:
        return await TransferSuggestionUseCase(self.session).list_for_document(
            workspace_id=workspace_id,
            raw_transactions=raw_transactions,
        )
