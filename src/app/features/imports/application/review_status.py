from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.processing import store_import_validation_result
from app.features.imports.domain.validation import validate_statement_totals
from app.features.imports.errors import RawTransactionReviewError
from app.features.imports.models import ParseAttempt, RawTransactionStatus, UploadedDocument
from app.features.imports.parsing.parser_types import StatementControlTotals
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

        await self._refresh_document_validation(document)
        await self.session.commit()
        return document

    async def _refresh_document_validation(self, document: UploadedDocument) -> None:
        attempt = latest_parse_attempt(document)
        if attempt is None:
            return
        control_totals = statement_control_totals_from_json(attempt.control_totals_json)
        report = validate_statement_totals(
            rows=document.raw_transactions,
            control_totals=control_totals,
        )
        await store_import_validation_result(
            self.imports,
            document,
            attempt,
            control_totals=control_totals,
            report=report,
        )


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


def latest_parse_attempt(document: UploadedDocument) -> ParseAttempt | None:
    if not document.parse_attempts:
        return None
    return document.parse_attempts[0]


def statement_control_totals_from_json(
    payload: dict[str, object] | None,
) -> StatementControlTotals | None:
    if payload is None:
        return None
    currency = payload.get("currency")
    if not isinstance(currency, str):
        return None
    return StatementControlTotals(
        currency=currency,
        opening_balance=_decimal_from_json(payload.get("opening_balance")),
        closing_balance=_decimal_from_json(payload.get("closing_balance")),
        total_inflow=_decimal_from_json(payload.get("total_inflow")),
        total_outflow=_decimal_from_json(payload.get("total_outflow")),
    )


def _decimal_from_json(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, int):
        return Decimal(value)
    return None
