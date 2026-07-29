from collections.abc import Sequence
from uuid import UUID

from app.features.imports.models import RawTransaction
from app.features.imports.statements.dto import RawTransactionDraft


class RawTransactionMapper:
    @staticmethod
    def from_drafts(
        drafts: Sequence[RawTransactionDraft],
        *,
        workspace_id: UUID,
        uploaded_document_id: UUID,
        parse_attempt_id: UUID,
    ) -> list[RawTransaction]:
        return [
            RawTransactionMapper.from_draft(
                draft,
                workspace_id=workspace_id,
                uploaded_document_id=uploaded_document_id,
                parse_attempt_id=parse_attempt_id,
            )
            for draft in drafts
        ]

    @staticmethod
    def from_draft(
        draft: RawTransactionDraft,
        *,
        workspace_id: UUID,
        uploaded_document_id: UUID,
        parse_attempt_id: UUID,
    ) -> RawTransaction:
        return RawTransaction(
            workspace_id=workspace_id,
            uploaded_document_id=uploaded_document_id,
            parse_attempt_id=parse_attempt_id,
            **draft.model_dump(),
        )
