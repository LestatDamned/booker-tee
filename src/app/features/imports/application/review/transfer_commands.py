from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ledger.application.raw_transaction_posting import RawTransactionPoster
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


class ImportReviewTransferService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._poster = RawTransactionPoster(session)
        self._ledger = LedgerRepository(session)

    async def execute(
        self,
        *,
        context: WorkspaceContext,
        command: ImportReviewTransferCommand,
    ) -> ImportReviewTransferResult:
        replay = await self._find_replay(context=context, command=command)
        if replay is not None:
            return replay
        affected_documents = {command.document_id}
        updated_items = {command.item_id}
        try:
            if isinstance(command, CreateImportReviewTransferCommand):
                await self._poster.post_raw_transaction_as_transfer(
                    context=context,
                    document_id=command.document_id,
                    raw_transaction_id=command.item_id,
                    counterparty_account_id=command.counterparty_account_id,
                    matched_raw_transaction_id=None,
                    idempotency_key=command.idempotency_key,
                    idempotency_fingerprint=self._fingerprint(command),
                )
            elif isinstance(command, MatchImportReviewRawRowCommand):
                operation = await self._poster.post_raw_transaction_as_transfer(
                    context=context,
                    document_id=command.document_id,
                    raw_transaction_id=command.item_id,
                    counterparty_account_id=None,
                    matched_raw_transaction_id=command.matched_item_id,
                    idempotency_key=command.idempotency_key,
                    idempotency_fingerprint=self._fingerprint(command),
                )
                metadata = operation.extra_metadata or {}
                matched_document_id = metadata.get("matched_uploaded_document_id")
                if isinstance(matched_document_id, str):
                    affected_documents.add(UUID(matched_document_id))
                updated_items.add(command.matched_item_id)
            else:
                await self._poster.link_raw_transaction_to_existing_transfer(
                    context=context,
                    document_id=command.document_id,
                    raw_transaction_id=command.item_id,
                    operation_id=command.operation_id,
                )
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            replay = await self._find_replay(context=context, command=command)
            if replay is not None:
                return replay
            raise
        except Exception:
            await self._session.rollback()
            raise
        return ImportReviewTransferResult(
            updated_item_ids=frozenset(updated_items),
            affected_document_ids=frozenset(affected_documents),
        )

    async def _find_replay(
        self,
        *,
        context: WorkspaceContext,
        command: ImportReviewTransferCommand,
    ) -> ImportReviewTransferResult | None:
        if isinstance(command, LinkImportReviewExistingTransferCommand):
            row = await self._poster.imports.get_raw_transaction_for_workspace(
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
        if operation.idempotency_fingerprint != self._fingerprint(command):
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

    @staticmethod
    def _fingerprint(command: ImportReviewTransferCommand) -> str:
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
