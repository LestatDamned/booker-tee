"""Persistence queries owned by the import-review workflow."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.import_review.domain.posting import raw_transaction_effective_account_id
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.models import MoneyEntry, Operation


class ImportReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_manual_transfer_candidates_for_raw_transaction(
        self,
        *,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
        day_window: int = 3,
    ) -> list[Operation]:
        source_account_id = await self._raw_transaction_effective_account_id(
            workspace_id=workspace_id,
            raw_transaction=raw_transaction,
        )
        if (
            raw_transaction.amount is None
            or raw_transaction.currency is None
            or raw_transaction.operation_date is None
            or source_account_id is None
        ):
            return []

        result = await self.session.execute(
            select(Operation)
            .join(MoneyEntry)
            .options(
                selectinload(Operation.raw_transactions).selectinload(
                    RawTransaction.uploaded_document
                ),
                selectinload(Operation.money_entries).selectinload(MoneyEntry.account),
            )
            .where(
                Operation.workspace_id == workspace_id,
                Operation.source == OperationSource.MANUAL,
                Operation.type == OperationType.TRANSFER,
                Operation.status == OperationStatus.CONFIRMED,
                Operation.operation_date.between(
                    raw_transaction.operation_date - timedelta(days=day_window),
                    raw_transaction.operation_date + timedelta(days=day_window),
                ),
                MoneyEntry.account_id == source_account_id,
                MoneyEntry.amount == raw_transaction.amount,
                MoneyEntry.currency == raw_transaction.currency,
            )
            .order_by(Operation.operation_date, Operation.created_at)
        )
        return [
            operation
            for operation in result.unique().scalars().all()
            if not any(
                raw_transaction_effective_account_id(linked_raw) == source_account_id
                for linked_raw in operation.raw_transactions
            )
        ]

    async def list_manual_transfer_candidates_for_raw_transactions(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
        day_window: int = 3,
    ) -> list[Operation]:
        eligible = [
            raw_transaction
            for raw_transaction in raw_transactions
            if raw_transaction.linked_operation_id is None
            and raw_transaction.amount is not None
            and raw_transaction.currency is not None
            and raw_transaction.operation_date is not None
            and raw_transaction_effective_account_id(raw_transaction) is not None
        ]
        if not eligible:
            return []

        operation_dates = [
            raw_transaction.operation_date
            for raw_transaction in eligible
            if raw_transaction.operation_date is not None
        ]
        source_account_ids = {
            account_id
            for raw_transaction in eligible
            if (account_id := raw_transaction_effective_account_id(raw_transaction)) is not None
        }
        amounts = {
            raw_transaction.amount
            for raw_transaction in eligible
            if raw_transaction.amount is not None
        }
        currencies = {
            raw_transaction.currency
            for raw_transaction in eligible
            if raw_transaction.currency is not None
        }
        result = await self.session.execute(
            select(Operation)
            .join(MoneyEntry)
            .options(
                selectinload(Operation.raw_transactions).selectinload(
                    RawTransaction.uploaded_document
                ),
                selectinload(Operation.money_entries).selectinload(MoneyEntry.account),
            )
            .where(
                Operation.workspace_id == workspace_id,
                Operation.source == OperationSource.MANUAL,
                Operation.type == OperationType.TRANSFER,
                Operation.status == OperationStatus.CONFIRMED,
                Operation.operation_date.between(
                    min(operation_dates) - timedelta(days=day_window),
                    max(operation_dates) + timedelta(days=day_window),
                ),
                MoneyEntry.account_id.in_(source_account_ids),
                MoneyEntry.amount.in_(amounts),
                MoneyEntry.currency.in_(currencies),
            )
            .order_by(Operation.operation_date, Operation.created_at)
        )
        return list(result.unique().scalars().all())

    async def _raw_transaction_effective_account_id(
        self,
        *,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
    ) -> UUID | None:
        account_id = raw_transaction_effective_account_id(raw_transaction)
        if account_id is not None:
            return account_id
        result = await self.session.execute(
            select(UploadedDocument.account_id).where(
                UploadedDocument.id == raw_transaction.uploaded_document_id,
                UploadedDocument.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()
