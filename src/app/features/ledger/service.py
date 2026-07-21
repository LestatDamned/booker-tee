from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.repository import AccountRepository
from app.features.imports.models import RawTransaction
from app.features.ledger.application.commands import (
    UpdateImportedOperationReviewFieldsCommand,
)
from app.features.ledger.application.imported_operation_review import ImportedOperationReviewUseCase
from app.features.ledger.application.imported_operation_undo import ImportedOperationUndoUseCase
from app.features.ledger.application.listing import (
    AccountEntryFilters,
    LedgerPage,
    LedgerPagination,
    normalize_pagination,
)
from app.features.ledger.application.raw_transaction_posting import RawTransactionPostingUseCase
from app.features.ledger.application.transfer_suggestions import (
    ExistingTransferSuggestion,
    TransferSuggestion,
    TransferSuggestionUseCase,
)
from app.features.ledger.mapping.dto import (
    AccountLedgerDetailView,
    LedgerViewMapper,
    OperationRefView,
)
from app.features.ledger.models import Operation, OperationSource
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


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
        filters: AccountEntryFilters | None = None,
        pagination: LedgerPagination | None = None,
    ) -> AccountLedgerDetailView | None:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            return None
        normalized_filters = filters or AccountEntryFilters()
        normalized_pagination = pagination or normalize_pagination(1, 50)
        entries_total = await self.ledger.get_confirmed_account_entries_total(
            workspace_id=workspace_id,
            account_id=account_id,
        )
        matching_count = await self.ledger.count_account_entries(
            workspace_id=workspace_id,
            account_id=account_id,
            filters=normalized_filters,
        )
        entries = await self.ledger.list_account_entries(
            workspace_id=workspace_id,
            account_id=account_id,
            filters=normalized_filters,
            pagination=normalized_pagination,
        )
        return LedgerViewMapper.account_detail_from_parts(
            account=account,
            balance=(account.initial_balance + entries_total).quantize(Decimal("0.01")),
            entries=entries,
            page=LedgerPage(
                page=normalized_pagination.page,
                per_page=normalized_pagination.per_page,
                total=matching_count,
            ),
        )

    async def get_imported_operation_review(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
        account_id: UUID | None = None,
    ) -> OperationRefView | None:
        operation = await self.ledger.get_operation_for_workspace(workspace_id, operation_id)
        if operation is None or operation.source != OperationSource.BANK_PDF:
            return None
        if account_id is not None and all(
            entry.account_id != account_id for entry in operation.money_entries
        ):
            return None
        return LedgerViewMapper.operation_ref_from_model(operation)

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

    async def update_imported_operation_review_fields(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateImportedOperationReviewFieldsCommand,
    ) -> Operation:
        return await ImportedOperationReviewUseCase(self.session).update_review_fields(
            context=context,
            command=command,
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

    async def link_raw_transaction_to_existing_transfer(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        operation_id: UUID,
    ) -> Operation:
        return await RawTransactionPostingUseCase(
            self.session,
        ).link_raw_transaction_to_existing_transfer(
            context=context,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            operation_id=operation_id,
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

    async def list_existing_transfer_suggestions_for_document(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> dict[UUID, list[ExistingTransferSuggestion]]:
        return await TransferSuggestionUseCase(self.session).list_existing_manual_for_document(
            workspace_id=workspace_id,
            raw_transactions=raw_transactions,
        )
