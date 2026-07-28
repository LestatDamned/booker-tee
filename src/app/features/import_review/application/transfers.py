"""Create and link transfers selected during import review."""

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.import_review.domain.posting import (
    ensure_matched_transfer_account,
    ensure_raw_transaction_can_post_as_transfer,
    require_raw_amount,
    require_raw_operation_date,
    require_raw_transaction_account_id,
)
from app.features.import_review.repository import ImportReviewRepository
from app.features.imports.application.documents.status import ImportedDocumentStatusUpdater
from app.features.imports.application.pipelines.document_validation import (
    refresh_document_validation,
)
from app.features.imports.models import RawTransaction
from app.features.imports.repository import ImportRepository
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.posting import LedgerPostingService
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class CreateImportReviewTransferCommand:
    document_id: UUID
    item_id: UUID
    counterparty_account_id: UUID
    idempotency_key: UUID


@dataclass(frozen=True)
class MatchImportReviewRawRowCommand:
    document_id: UUID
    item_id: UUID
    matched_item_id: UUID
    idempotency_key: UUID


@dataclass(frozen=True)
class LinkImportReviewExistingTransferCommand:
    document_id: UUID
    item_id: UUID
    operation_id: UUID
    idempotency_key: UUID


ImportReviewTransferCommand = (
    CreateImportReviewTransferCommand
    | MatchImportReviewRawRowCommand
    | LinkImportReviewExistingTransferCommand
)


@dataclass(frozen=True)
class ImportReviewTransferResult:
    updated_item_ids: frozenset[UUID]
    affected_document_ids: frozenset[UUID]


@dataclass(frozen=True)
class TransferCounterparty:
    account: Account
    amount: Decimal
    raw_transaction: RawTransaction | None


class ImportReviewTransferActor:
    def __init__(self, session: AsyncSession) -> None:
        self._imports = ImportRepository(session)
        self._review_repository = ImportReviewRepository(session)
        self._ledger = LedgerRepository(session)
        self._references = LedgerReferenceResolver(session)
        self._posting = LedgerPostingService(session)
        self._document_status = ImportedDocumentStatusUpdater(self._imports)

    async def apply(
        self,
        *,
        context: WorkspaceContext,
        command: ImportReviewTransferCommand,
    ) -> ImportReviewTransferResult:
        replay = await self.find_replay(context=context, command=command)
        if replay is not None:
            return replay
        affected_documents = {command.document_id}
        updated_items = {command.item_id}
        if isinstance(command, CreateImportReviewTransferCommand):
            affected_documents.update(
                await self._post_transfer(
                    context=context,
                    document_id=command.document_id,
                    raw_transaction_id=command.item_id,
                    counterparty_account_id=command.counterparty_account_id,
                    matched_raw_transaction_id=None,
                    idempotency_key=command.idempotency_key,
                    idempotency_fingerprint=self.fingerprint(command),
                )
            )
        elif isinstance(command, MatchImportReviewRawRowCommand):
            affected_documents.update(
                await self._post_transfer(
                    context=context,
                    document_id=command.document_id,
                    raw_transaction_id=command.item_id,
                    counterparty_account_id=None,
                    matched_raw_transaction_id=command.matched_item_id,
                    idempotency_key=command.idempotency_key,
                    idempotency_fingerprint=self.fingerprint(command),
                )
            )
            updated_items.add(command.matched_item_id)
        else:
            await self._link_existing_transfer(
                context=context,
                document_id=command.document_id,
                raw_transaction_id=command.item_id,
                operation_id=command.operation_id,
            )
        return ImportReviewTransferResult(
            updated_item_ids=frozenset(updated_items),
            affected_document_ids=frozenset(affected_documents),
        )

    async def find_replay(
        self,
        *,
        context: WorkspaceContext,
        command: ImportReviewTransferCommand,
    ) -> ImportReviewTransferResult | None:
        if isinstance(command, LinkImportReviewExistingTransferCommand):
            row = await self._imports.get_raw_transaction_for_workspace(
                context.workspace.id,
                command.document_id,
                command.item_id,
            )
            if row is not None and row.linked_operation_id == command.operation_id:
                return ImportReviewTransferResult(
                    updated_item_ids=frozenset({command.item_id}),
                    affected_document_ids=frozenset({command.document_id}),
                )
            return None

        operation = await self._ledger.get_operation_by_idempotency_key(
            workspace_id=context.workspace.id,
            idempotency_key=command.idempotency_key,
        )
        if operation is None:
            return None
        if operation.idempotency_fingerprint != self.fingerprint(command):
            raise LedgerPostingError("Idempotency key was already used with another payload.")
        metadata = operation.extra_metadata or {}
        document_ids = {command.document_id}
        matched_document_id = metadata.get("matched_uploaded_document_id")
        if isinstance(matched_document_id, str):
            document_ids.add(UUID(matched_document_id))
        item_ids = {command.item_id}
        matched_item_id = metadata.get("matched_raw_transaction_id")
        if isinstance(matched_item_id, str):
            item_ids.add(UUID(matched_item_id))
        return ImportReviewTransferResult(
            updated_item_ids=frozenset(item_ids),
            affected_document_ids=frozenset(document_ids),
        )

    async def _post_transfer(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        counterparty_account_id: UUID | None,
        matched_raw_transaction_id: UUID | None,
        idempotency_key: UUID,
        idempotency_fingerprint: str,
    ) -> set[UUID]:
        raw_transaction, matched_raw_transaction = await self._load_transfer_rows(
            workspace_id=context.workspace.id,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            matched_raw_transaction_id=matched_raw_transaction_id,
        )
        ensure_raw_transaction_can_post_as_transfer(raw_transaction)
        source_account = await self._references.get_account(
            context.workspace.id,
            require_raw_transaction_account_id(raw_transaction),
        )
        matched_raw_transaction = await self._resolve_matched_transfer_row(
            context.workspace.id,
            raw_transaction,
            matched_raw_transaction_id,
            matched_raw_transaction,
        )
        counterparty = await self._resolve_transfer_counterparty(
            workspace_id=context.workspace.id,
            source_raw_transaction=raw_transaction,
            source_account=source_account,
            counterparty_account_id=counterparty_account_id,
            matched_raw_transaction=matched_raw_transaction,
        )
        operation = await self._posting.post_imported_transfer(
            context=context,
            source_account=source_account,
            source_amount=require_raw_amount(raw_transaction),
            source_balance_after=raw_transaction.balance_after,
            counterparty_account=counterparty.account,
            counterparty_amount=counterparty.amount,
            counterparty_balance_after=(
                counterparty.raw_transaction.balance_after
                if counterparty.raw_transaction is not None
                else None
            ),
            operation_date=require_raw_operation_date(raw_transaction),
            posting_date=raw_transaction.posting_date,
            description=(raw_transaction.description_normalized or raw_transaction.description_raw),
            transfer_category=await self._references.get_transfer_category(context.workspace.id),
            extra_metadata={
                "source": "raw_transfer",
                "raw_transaction_id": str(raw_transaction.id),
                "matched_raw_transaction_id": (
                    str(counterparty.raw_transaction.id)
                    if counterparty.raw_transaction is not None
                    else None
                ),
                "matched_uploaded_document_id": (
                    str(counterparty.raw_transaction.uploaded_document_id)
                    if counterparty.raw_transaction is not None
                    else None
                ),
            },
            idempotency_key=idempotency_key,
            idempotency_fingerprint=idempotency_fingerprint,
        )
        await self._imports.link_raw_transaction_to_operation(
            raw_transaction,
            operation_id=operation.id,
        )
        affected_document_ids = {document_id}
        if counterparty.raw_transaction is not None:
            await self._imports.link_raw_transaction_to_operation(
                counterparty.raw_transaction,
                operation_id=operation.id,
            )
            affected_document_ids.add(counterparty.raw_transaction.uploaded_document_id)
        await self._refresh_documents(
            workspace_id=context.workspace.id,
            document_ids=affected_document_ids,
        )
        return affected_document_ids

    async def _load_transfer_rows(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        raw_transaction_id: UUID,
        matched_raw_transaction_id: UUID | None,
    ) -> tuple[RawTransaction, RawTransaction | None]:
        matched_raw_transaction = None
        if matched_raw_transaction_id is not None:
            locked_rows = await self._imports.lock_raw_transactions_for_workspace(
                workspace_id=workspace_id,
                raw_transaction_ids={raw_transaction_id, matched_raw_transaction_id},
            )
            rows_by_id = {row.id: row for row in locked_rows}
            raw_transaction = rows_by_id.get(raw_transaction_id)
            matched_raw_transaction = rows_by_id.get(matched_raw_transaction_id)
            if raw_transaction is not None and (
                raw_transaction.uploaded_document_id != document_id
            ):
                raw_transaction = None
        else:
            raw_transaction = await self._imports.get_raw_transaction_for_workspace(
                workspace_id,
                document_id,
                raw_transaction_id,
            )
        if raw_transaction is None:
            raise LedgerPostingError("Raw transaction row was not found.")
        return raw_transaction, matched_raw_transaction

    async def _resolve_matched_transfer_row(
        self,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
        matched_raw_transaction_id: UUID | None,
        matched_raw_transaction: RawTransaction | None,
    ) -> RawTransaction | None:
        if matched_raw_transaction_id is None:
            return None
        if matched_raw_transaction is None:
            matched_raw_transaction = await self._imports.get_raw_transaction_by_id_for_workspace(
                workspace_id,
                matched_raw_transaction_id,
            )
        if matched_raw_transaction is None:
            raise LedgerPostingError("Matched raw transaction row was not found.")
        candidates = await self._imports.list_transfer_candidate_raw_transactions(
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
                account=await self._references.get_account(
                    workspace_id,
                    require_raw_transaction_account_id(matched_raw_transaction),
                ),
                amount=require_raw_amount(matched_raw_transaction),
                raw_transaction=matched_raw_transaction,
            )
        if counterparty_account_id is None:
            raise LedgerPostingError("Transfer account is required.")
        return TransferCounterparty(
            account=await self._references.get_account(
                workspace_id,
                counterparty_account_id,
            ),
            amount=-require_raw_amount(source_raw_transaction),
            raw_transaction=None,
        )

    async def _link_existing_transfer(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        operation_id: UUID,
    ) -> None:
        raw_transaction = await self._imports.get_raw_transaction_for_workspace(
            context.workspace.id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise LedgerPostingError("Raw transaction row was not found.")
        ensure_raw_transaction_can_post_as_transfer(raw_transaction)
        locked_operation = await self._ledger.get_operation_for_workspace_for_update(
            workspace_id=context.workspace.id,
            operation_id=operation_id,
        )
        if locked_operation is None:
            raise LedgerPostingError("Manual transfer is not a transfer candidate.")
        candidates = (
            await self._review_repository.list_manual_transfer_candidates_for_raw_transaction(
                workspace_id=context.workspace.id,
                raw_transaction=raw_transaction,
            )
        )
        operation = next(
            (candidate for candidate in candidates if candidate.id == operation_id),
            None,
        )
        if operation is None:
            raise LedgerPostingError("Manual transfer is not a transfer candidate.")
        await self._imports.link_raw_transaction_to_operation(
            raw_transaction,
            operation_id=operation.id,
        )
        await self._refresh_documents(
            workspace_id=context.workspace.id,
            document_ids={document_id},
        )

    async def _refresh_documents(
        self,
        *,
        workspace_id: UUID,
        document_ids: set[UUID],
    ) -> None:
        for document_id in document_ids:
            document = await self._imports.get_document_for_workspace(
                workspace_id,
                document_id,
            )
            if document is not None:
                await refresh_document_validation(self._imports, document)
            await self._document_status.mark_imported_if_complete(
                workspace_id=workspace_id,
                document_id=document_id,
            )

    @staticmethod
    def fingerprint(command: ImportReviewTransferCommand) -> str:
        if isinstance(command, CreateImportReviewTransferCommand):
            payload = (
                f"new_transfer:{command.document_id}:{command.item_id}:"
                f"{command.counterparty_account_id}"
            )
        elif isinstance(command, MatchImportReviewRawRowCommand):
            payload = (
                f"raw_row_match:{command.document_id}:{command.item_id}:{command.matched_item_id}"
            )
        else:
            payload = (
                f"existing_operation_link:{command.document_id}:{command.item_id}:"
                f"{command.operation_id}"
            )
        return sha256(payload.encode()).hexdigest()


class ImportReviewTransferService:
    def __init__(
        self,
        session: AsyncSession,
        actor: ImportReviewTransferActor | None = None,
    ) -> None:
        self._session = session
        self._actor = actor or ImportReviewTransferActor(session)

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        command: ImportReviewTransferCommand,
    ) -> ImportReviewTransferResult:
        try:
            result = await self._actor.apply(context=context, command=command)
            await self._session.commit()
            return result
        except IntegrityError:
            await self._session.rollback()
            replay = await self._actor.find_replay(context=context, command=command)
            if replay is not None:
                return replay
            raise
        except Exception:
            await self._session.rollback()
            raise
