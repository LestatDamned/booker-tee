from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus


class StatementRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_raw_transactions(
        self,
        raw_transactions: list[RawTransaction],
    ) -> list[RawTransaction]:
        self.session.add_all(raw_transactions)
        await self.session.flush()
        return raw_transactions

    async def find_existing_dedupe_hashes(
        self,
        *,
        workspace_id: UUID,
        dedupe_hashes: set[str],
        exclude_document_id: UUID | None = None,
    ) -> set[str]:
        if not dedupe_hashes:
            return set()
        query = select(RawTransaction.dedupe_hash).where(
            RawTransaction.workspace_id == workspace_id,
            RawTransaction.dedupe_hash.in_(dedupe_hashes),
            RawTransaction.status.not_in(
                [
                    RawTransactionStatus.DUPLICATE,
                    RawTransactionStatus.IGNORED,
                    RawTransactionStatus.FAILED,
                ]
            ),
        )
        if exclude_document_id is not None:
            query = query.where(RawTransaction.uploaded_document_id != exclude_document_id)

        result = await self.session.execute(query)
        return {value for value in result.scalars().all() if value is not None}

    async def find_existing_possible_duplicate_fingerprints(
        self,
        *,
        workspace_id: UUID,
        fingerprints: set[tuple[UUID, date, Decimal, str]],
        exclude_document_id: UUID | None = None,
    ) -> set[tuple[UUID, date, Decimal, str]]:
        if not fingerprints:
            return set()

        account_ids = {fingerprint[0] for fingerprint in fingerprints}
        operation_dates = {fingerprint[1] for fingerprint in fingerprints}
        amounts = {fingerprint[2] for fingerprint in fingerprints}
        currencies = {fingerprint[3] for fingerprint in fingerprints}
        query = select(
            RawTransaction.account_id,
            RawTransaction.operation_date,
            RawTransaction.amount,
            RawTransaction.currency,
        ).where(
            RawTransaction.workspace_id == workspace_id,
            RawTransaction.account_id.in_(account_ids),
            RawTransaction.operation_date.in_(operation_dates),
            RawTransaction.amount.in_(amounts),
            RawTransaction.currency.in_(currencies),
            RawTransaction.status.not_in(
                [
                    RawTransactionStatus.DUPLICATE,
                    RawTransactionStatus.IGNORED,
                    RawTransactionStatus.FAILED,
                ]
            ),
        )
        if exclude_document_id is not None:
            query = query.where(RawTransaction.uploaded_document_id != exclude_document_id)

        result = await self.session.execute(query)
        matches: set[tuple[UUID, date, Decimal, str]] = set()
        for account_id, operation_date, amount, currency in result.all():
            if account_id and operation_date and amount is not None and currency:
                fingerprint = (account_id, operation_date, amount, currency)
                if fingerprint in fingerprints:
                    matches.add(fingerprint)
        return matches

    async def mark_reviewable_rows_superseded(
        self,
        document: UploadedDocument,
    ) -> None:
        for raw_transaction in document.raw_transactions:
            if raw_transaction.status in {
                RawTransactionStatus.CONFIRMED,
                RawTransactionStatus.IGNORED,
                RawTransactionStatus.DUPLICATE,
            }:
                continue
            raw_transaction.status = RawTransactionStatus.DUPLICATE
        await self.session.flush()
