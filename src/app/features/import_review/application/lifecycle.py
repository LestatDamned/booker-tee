"""Apply user-selected lifecycle transitions to import review rows."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.import_review.domain.lifecycle import (
    ImportReviewLifecycleAction,
    resolve_import_review_lifecycle_transition,
)
from app.features.import_review.repository import ImportReviewRepository
from app.features.imports.application.pipelines.document_validation import (
    refresh_document_validation,
)
from app.features.imports.documents.lifecycle import ImportedDocumentStatusUpdater
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.errors import RawTransactionReviewError


@dataclass(frozen=True)
class ImportReviewLifecycleCommand:
    document_id: UUID
    item_id: UUID
    action: ImportReviewLifecycleAction
    expected_status: RawTransactionStatus


@dataclass(frozen=True)
class ImportReviewLifecycleResult:
    item_id: UUID
    document_id: UUID
    replayed: bool


class ImportReviewLifecycleActor:
    def __init__(self, session: AsyncSession) -> None:
        self._documents = DocumentRepository(session)
        self._review_repository = ImportReviewRepository(session)

    async def apply(
        self,
        *,
        workspace_id: UUID,
        command: ImportReviewLifecycleCommand,
    ) -> ImportReviewLifecycleResult:
        row = await self._review_repository.get_raw_transaction_for_workspace(
            workspace_id,
            command.document_id,
            command.item_id,
        )
        if row is None:
            raise RawTransactionReviewError("Raw transaction row was not found.")
        transition = resolve_import_review_lifecycle_transition(
            status=row.status,
            linked_operation_id=row.linked_operation_id,
            action=command.action,
            expected_status=command.expected_status,
        )
        if not transition.replayed:
            await self._review_repository.mark_raw_transaction_status(
                row,
                transition.target_status,
            )
        document = await self._documents.get_document_for_workspace_for_update(
            workspace_id,
            command.document_id,
        )
        if document is None:
            raise RawTransactionReviewError("Document was not found.")
        await refresh_document_validation(self._documents, document)
        await ImportedDocumentStatusUpdater(self._documents).sync_review_status(document)
        return ImportReviewLifecycleResult(
            item_id=row.id,
            document_id=document.id,
            replayed=transition.replayed,
        )


class ImportReviewLifecycleService:
    def __init__(
        self,
        session: AsyncSession,
        actor: ImportReviewLifecycleActor | None = None,
    ) -> None:
        self._session = session
        self._actor = actor or ImportReviewLifecycleActor(session)

    async def execute(
        self,
        *,
        workspace_id: UUID,
        command: ImportReviewLifecycleCommand,
    ) -> ImportReviewLifecycleResult:
        try:
            result = await self._actor.apply(
                workspace_id=workspace_id,
                command=command,
            )
            await self._session.commit()
            return result
        except Exception:
            await self._session.rollback()
            raise
