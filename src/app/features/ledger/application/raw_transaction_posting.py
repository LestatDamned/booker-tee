from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.imports.models import RawTransaction
from app.features.imports.repository import ImportRepository
from app.features.ledger.application.imported_document_status import ImportedDocumentStatusUpdater
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.domain.money import (
    ensure_balanced_transfer,
    ensure_distinct_accounts,
    ensure_same_currency,
)
from app.features.ledger.domain.raw_transactions import (
    LedgerPostingPlan,
    ensure_matched_transfer_account,
    ensure_raw_transaction_can_post_as_transfer,
    require_raw_amount,
)
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.mapping.operation_factory import (
    build_bank_pdf_operation,
    build_bank_pdf_transfer_operation,
    build_money_entry,
)
from app.features.ledger.models import Operation
from app.features.ledger.repository import LedgerRepository
from app.features.transaction_rules.domain.suggestions import rule_suggestion_auto_applies
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class TransferCounterparty:
    account: Account
    amount: Decimal
    raw_transaction: RawTransaction | None


class RawTransactionPostingUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)
        self.ledger = LedgerRepository(session)
        self.references = LedgerReferenceResolver(session)
        self.document_status = ImportedDocumentStatusUpdater(self.imports)

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
            source_account = await self.references.get_account_for_raw_transaction(
                context.workspace.id,
                raw_transaction,
            )
            matched_raw_transaction = await self._resolve_matched_transfer_row(
                context.workspace.id,
                raw_transaction,
                matched_raw_transaction_id,
            )
            counterparty = await self._resolve_transfer_counterparty(
                workspace_id=context.workspace.id,
                source_raw_transaction=raw_transaction,
                source_account=source_account,
                counterparty_account_id=counterparty_account_id,
                matched_raw_transaction=matched_raw_transaction,
            )
            ensure_same_currency(source_account, counterparty.account)
            ensure_balanced_transfer(require_raw_amount(raw_transaction), counterparty.amount)
            transfer_category = await self.references.get_transfer_category(context.workspace.id)
            operation = await self.ledger.create_operation(
                build_bank_pdf_transfer_operation(
                    context=context,
                    raw_transaction=raw_transaction,
                    matched_raw_transaction=counterparty.raw_transaction,
                    transfer_category=transfer_category,
                )
            )
            await self.ledger.create_money_entry(
                build_money_entry(
                    context=context,
                    operation=operation,
                    account=source_account,
                    amount=require_raw_amount(raw_transaction),
                    entry_order=1,
                    balance_after=raw_transaction.balance_after,
                )
            )
            await self.ledger.create_money_entry(
                build_money_entry(
                    context=context,
                    operation=operation,
                    account=counterparty.account,
                    amount=counterparty.amount,
                    entry_order=2,
                    balance_after=counterparty.raw_transaction.balance_after
                    if counterparty.raw_transaction
                    else None,
                )
            )
            await self.imports.link_raw_transaction_to_operation(
                raw_transaction,
                operation_id=operation.id,
            )
            if counterparty.raw_transaction is not None:
                await self.imports.link_raw_transaction_to_operation(
                    counterparty.raw_transaction,
                    operation_id=operation.id,
                )
                await self.document_status.mark_imported_if_complete(
                    workspace_id=context.workspace.id,
                    document_id=counterparty.raw_transaction.uploaded_document_id,
                )
            await self.document_status.mark_imported_if_complete(
                workspace_id=context.workspace.id,
                document_id=document_id,
            )
            await self.session.commit()
            return operation
        except Exception:
            await self.session.rollback()
            raise

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

        account = await self.references.get_account(
            context.workspace.id,
            raw_transaction.account_id,
        )
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

        plan = LedgerPostingPlan.from_raw_transaction(raw_transaction, account)
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
        category = await self.references.get_category_or_uncategorized(
            context.workspace.id,
            category_id or suggested_category_id,
        )
        property_ = await self.references.get_property(
            context.workspace.id,
            property_id or suggested_property_id,
        )
        operation = await self.ledger.create_operation(
            build_bank_pdf_operation(
                context=context,
                document_id=document_id,
                raw_transaction=raw_transaction,
                plan=plan,
                category=category,
                property_=property_,
            )
        )
        await self.ledger.create_money_entry(
            build_money_entry(
                context=context,
                operation=operation,
                account=account,
                amount=plan.amount,
                entry_order=1,
                balance_after=plan.balance_after,
                extra_metadata={"source": "bank_pdf"},
            )
        )
        await self.imports.link_raw_transaction_to_operation(
            raw_transaction,
            operation_id=operation.id,
        )
        await self.document_status.mark_imported_if_complete(
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
        return operation

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

    async def _resolve_transfer_counterparty(
        self,
        *,
        workspace_id: UUID,
        source_raw_transaction: RawTransaction,
        source_account: Account,
        counterparty_account_id: UUID | None,
        matched_raw_transaction: RawTransaction | None,
    ) -> TransferCounterparty:
        if matched_raw_transaction is not None:
            ensure_raw_transaction_can_post_as_transfer(matched_raw_transaction)
            ensure_matched_transfer_account(matched_raw_transaction, counterparty_account_id)
            return TransferCounterparty(
                account=await self.references.get_account_for_raw_transaction(
                    workspace_id,
                    matched_raw_transaction,
                ),
                amount=require_raw_amount(matched_raw_transaction),
                raw_transaction=matched_raw_transaction,
            )

        if counterparty_account_id is None:
            raise LedgerPostingError("Transfer account is required.")
        counterparty_account = await self.references.get_account(
            workspace_id,
            counterparty_account_id,
        )
        ensure_distinct_accounts(source_account.id, counterparty_account.id)
        return TransferCounterparty(
            account=counterparty_account,
            amount=-require_raw_amount(source_raw_transaction),
            raw_transaction=None,
        )
