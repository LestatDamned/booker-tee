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
from app.features.imports.errors import RawTransactionReviewError
from app.features.imports.models import RawTransactionStatus, UploadedDocument
from app.features.imports.repository import ImportRepository


class RawTransactionReviewStatusUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)

    async def set_status(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        raw_transaction_id: UUID,
        action: str,
    ) -> UploadedDocument:
        lifecycle_action = lifecycle_action_for_legacy_review_action(action)
        raw_transaction = await self.imports.get_raw_transaction_for_workspace(
            workspace_id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise RawTransactionReviewError("Raw transaction row was not found.")

        transition = resolve_import_review_lifecycle_transition(
            status=raw_transaction.status,
            linked_operation_id=getattr(raw_transaction, "linked_operation_id", None),
            action=lifecycle_action,
            expected_status=raw_transaction.status,
        )
        if not transition.replayed:
            await self.imports.mark_raw_transaction_status(
                raw_transaction,
                transition.target_status,
            )
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise RawTransactionReviewError("Document was not found.")

        await refresh_document_validation(self.imports, document)
        await ImportedDocumentStatusUpdater(self.imports).sync_review_status(document)
        return document


def raw_transaction_status_for_review_action(action: str) -> RawTransactionStatus:
    return {
        ImportReviewLifecycleAction.MARK_DUPLICATE: RawTransactionStatus.DUPLICATE,
        ImportReviewLifecycleAction.IGNORE: RawTransactionStatus.IGNORED,
        ImportReviewLifecycleAction.MARK_UNIQUE: RawTransactionStatus.MATCHED,
        ImportReviewLifecycleAction.NEEDS_REVIEW: RawTransactionStatus.NEEDS_REVIEW,
    }[lifecycle_action_for_legacy_review_action(action)]


def lifecycle_action_for_legacy_review_action(action: str) -> ImportReviewLifecycleAction:
    action_map = {
        "duplicate": ImportReviewLifecycleAction.MARK_DUPLICATE,
        "ignore": ImportReviewLifecycleAction.IGNORE,
        "mark_unique": ImportReviewLifecycleAction.MARK_UNIQUE,
        "needs_review": ImportReviewLifecycleAction.NEEDS_REVIEW,
    }
    try:
        return action_map[action]
    except KeyError as exc:
        raise RawTransactionReviewError(f"Unsupported review action: {action}") from exc
