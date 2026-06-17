from collections.abc import Sequence
from uuid import UUID

from app.features.imports.models import RawTransaction
from app.features.imports.parser_types import RawTransactionDraft


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
            row_index=draft.row_index,
            status=draft.status,
            raw_payload=draft.raw_payload,
            operation_date_raw=draft.operation_date_raw,
            posting_date_raw=draft.posting_date_raw,
            description_raw=draft.description_raw,
            amount_raw=draft.amount_raw,
            currency_raw=draft.currency_raw,
            balance_after_raw=draft.balance_after_raw,
            account_hint_raw=draft.account_hint_raw,
            account_id=draft.account_id,
            operation_date=draft.operation_date,
            posting_date=draft.posting_date,
            description_normalized=draft.description_normalized,
            amount=draft.amount,
            currency=draft.currency,
            balance_after=draft.balance_after,
            dedupe_hash=draft.dedupe_hash,
            confidence_score=draft.confidence_score,
            normalization_error=draft.normalization_error,
        )
