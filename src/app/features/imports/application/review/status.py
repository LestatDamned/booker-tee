from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.review.validation_refresh import (
    refresh_document_validation,
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
        target_status = raw_transaction_status_for_review_action(action)
        raw_transaction = await self.imports.get_raw_transaction_for_workspace(
            workspace_id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise RawTransactionReviewError("Raw transaction row was not found.")

        await self.imports.mark_raw_transaction_status(raw_transaction, target_status)
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise RawTransactionReviewError("Document was not found.")

        await refresh_document_validation(self.imports, document)
        await self.session.commit()
        return document


def raw_transaction_status_for_review_action(action: str) -> RawTransactionStatus:
    action_map = {
        "ignore": RawTransactionStatus.IGNORED,
        "mark_unique": RawTransactionStatus.MATCHED,
        "needs_review": RawTransactionStatus.NEEDS_REVIEW,
    }
    try:
        return action_map[action]
    except KeyError as exc:
        raise RawTransactionReviewError(f"Unsupported review action: {action}") from exc
