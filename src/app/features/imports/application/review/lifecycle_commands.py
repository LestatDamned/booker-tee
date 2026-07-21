from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.documents.status import ImportedDocumentStatusUpdater
from app.features.imports.application.review.validation_refresh import (
    refresh_document_validation,
)
from app.features.imports.domain.review_lifecycle import (
    ImportReviewLifecycleAction,
    resolve_import_review_lifecycle_transition,
)
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.errors import RawTransactionReviewError
from app.features.imports.repository import ImportRepository


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


class ImportReviewLifecycleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._imports = ImportRepository(session)

    async def execute(
        self,
        *,
        workspace_id: UUID,
        command: ImportReviewLifecycleCommand,
    ) -> ImportReviewLifecycleResult:
        try:
            row = await self._imports.get_raw_transaction_for_workspace(
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
                await self._imports.mark_raw_transaction_status(
                    row,
                    transition.target_status,
                )
            document = await self._imports.get_document_for_workspace_for_update(
                workspace_id,
                command.document_id,
            )
            if document is None:
                raise RawTransactionReviewError("Document was not found.")
            await refresh_document_validation(self._imports, document)
            await ImportedDocumentStatusUpdater(self._imports).sync_review_status(document)
            await self._session.commit()
            return ImportReviewLifecycleResult(
                item_id=row.id,
                document_id=document.id,
                replayed=transition.replayed,
            )
        except Exception:
            await self._session.rollback()
            raise
