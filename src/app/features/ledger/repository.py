from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.ledger.application.listing import (
    AccountEntryFilters,
    LedgerPagination,
    ManualOperationFilters,
)
from app.features.ledger.domain.raw_transactions import raw_transaction_effective_account_id
from app.features.ledger.models import (
    MoneyEntry,
    Operation,
    OperationSource,
    OperationStatus,
    OperationType,
)


class LedgerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_operation(self, operation: Operation) -> Operation:
        self.session.add(operation)
        await self.session.flush()
        return operation

    async def create_money_entry(self, money_entry: MoneyEntry) -> MoneyEntry:
        self.session.add(money_entry)
        await self.session.flush()
        return money_entry

    async def get_operation_for_workspace(
        self,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> Operation | None:
        result = await self.session.execute(
            select(Operation)
            .options(
                selectinload(Operation.category),
                selectinload(Operation.property),
                selectinload(Operation.raw_transactions),
                selectinload(Operation.money_entries).selectinload(MoneyEntry.account),
            )
            .where(
                Operation.id == operation_id,
                Operation.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_operation_by_idempotency_key(
        self,
        *,
        workspace_id: UUID,
        idempotency_key: UUID,
    ) -> Operation | None:
        result = await self.session.execute(
            select(Operation)
            .options(
                selectinload(Operation.category),
                selectinload(Operation.property),
                selectinload(Operation.money_entries).selectinload(MoneyEntry.account),
            )
            .where(
                Operation.workspace_id == workspace_id,
                Operation.idempotency_key == str(idempotency_key),
            )
        )
        return result.scalar_one_or_none()

    async def list_manual_operations_page_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ManualOperationFilters,
        pagination: LedgerPagination,
    ) -> list[Operation]:
        query = (
            select(Operation)
            .options(
                selectinload(Operation.category),
                selectinload(Operation.property),
                selectinload(Operation.money_entries).selectinload(MoneyEntry.account),
            )
            .where(
                Operation.workspace_id == workspace_id,
                Operation.source == OperationSource.MANUAL,
            )
        )
        query = self._apply_manual_operation_filters(query, filters)
        query = query.order_by(
            Operation.operation_date.desc(),
            Operation.created_at.desc(),
            Operation.id.desc(),
        )
        result = await self.session.execute(
            query.offset(pagination.offset).limit(pagination.per_page)
        )
        return list(result.unique().scalars().all())

    async def count_manual_operations_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ManualOperationFilters,
    ) -> int:
        query = select(func.count(func.distinct(Operation.id))).where(
            Operation.workspace_id == workspace_id,
            Operation.source == OperationSource.MANUAL,
        )
        query = self._apply_manual_operation_filters(query, filters)
        result = await self.session.execute(query)
        return result.scalar_one()

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

    async def delete_operation(self, operation: Operation) -> None:
        await self.session.delete(operation)
        await self.session.flush()

    async def list_account_entries(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        filters: AccountEntryFilters | None = None,
        pagination: LedgerPagination | None = None,
    ) -> list[MoneyEntry]:
        query = (
            select(MoneyEntry)
            .options(
                selectinload(MoneyEntry.account),
                selectinload(MoneyEntry.operation).selectinload(Operation.category),
                selectinload(MoneyEntry.operation).selectinload(Operation.property),
                selectinload(MoneyEntry.operation).selectinload(Operation.raw_transactions),
                selectinload(MoneyEntry.operation)
                .selectinload(Operation.money_entries)
                .selectinload(MoneyEntry.account),
            )
            .join(Operation)
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == account_id,
                Operation.workspace_id == workspace_id,
            )
        )
        query = self._apply_account_entry_filters(query, filters or AccountEntryFilters())
        query = query.order_by(
            Operation.operation_date.desc(),
            Operation.created_at.desc(),
            Operation.id.desc(),
            MoneyEntry.created_at.desc(),
            MoneyEntry.id.desc(),
        )
        if pagination is not None:
            query = query.offset(pagination.offset).limit(pagination.per_page)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_account_entries(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        filters: AccountEntryFilters,
    ) -> int:
        query = (
            select(func.count(MoneyEntry.id))
            .join(Operation)
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == account_id,
                Operation.workspace_id == workspace_id,
            )
        )
        query = self._apply_account_entry_filters(query, filters)
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_confirmed_account_entries_total(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        date_to: date | None = None,
    ) -> Decimal:
        query = (
            select(func.coalesce(func.sum(MoneyEntry.amount), Decimal("0.00")))
            .join(Operation)
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == account_id,
                Operation.workspace_id == workspace_id,
                Operation.status == OperationStatus.CONFIRMED,
            )
        )
        if date_to is not None:
            query = query.where(Operation.operation_date <= date_to)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def list_confirmed_operations_for_report(
        self,
        *,
        workspace_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: UUID | None = None,
        category_id: UUID | None = None,
        property_id: UUID | None = None,
    ) -> list[Operation]:
        query = (
            select(Operation)
            .options(
                selectinload(Operation.money_entries),
                selectinload(Operation.money_entries).selectinload(MoneyEntry.account),
                selectinload(Operation.category),
                selectinload(Operation.property),
            )
            .where(
                Operation.workspace_id == workspace_id,
                Operation.status == OperationStatus.CONFIRMED,
            )
            .order_by(Operation.operation_date.desc(), Operation.created_at.desc())
        )
        if account_id is not None:
            query = query.join(MoneyEntry).where(MoneyEntry.account_id == account_id)
        if category_id is not None:
            query = query.where(Operation.category_id == category_id)
        if property_id is not None:
            query = query.where(Operation.property_id == property_id)
        if date_from is not None:
            query = query.where(Operation.operation_date >= date_from)
        if date_to is not None:
            query = query.where(Operation.operation_date <= date_to)

        result = await self.session.execute(query)
        return list(result.unique().scalars().all())

    def _apply_account_entry_filters(
        self,
        query: Select[tuple[MoneyEntry]] | Select[tuple[int]],
        filters: AccountEntryFilters,
    ) -> Select[tuple[MoneyEntry]] | Select[tuple[int]]:
        if filters.status is not None:
            query = query.where(Operation.status == filters.status)
        if filters.source is not None:
            query = query.where(Operation.source == filters.source)
        if filters.operation_type is not None:
            query = query.where(Operation.type == filters.operation_type)
        if filters.category_id is not None:
            query = query.where(Operation.category_id == filters.category_id)
        if filters.property_id is not None:
            query = query.where(Operation.property_id == filters.property_id)
        if filters.date_from is not None:
            query = query.where(Operation.operation_date >= filters.date_from)
        if filters.date_to is not None:
            query = query.where(Operation.operation_date <= filters.date_to)
        if filters.search:
            query = query.where(Operation.description.ilike(f"%{filters.search}%"))
        return query

    def _apply_manual_operation_filters(
        self,
        query: Select[tuple[Operation]] | Select[tuple[int]],
        filters: ManualOperationFilters,
    ) -> Select[tuple[Operation]] | Select[tuple[int]]:
        if filters.status is not None:
            query = query.where(Operation.status == filters.status)
        if filters.operation_type is not None:
            query = query.where(Operation.type == filters.operation_type)
        if filters.category_id is not None:
            query = query.where(Operation.category_id == filters.category_id)
        if filters.property_id is not None:
            query = query.where(Operation.property_id == filters.property_id)
        if filters.date_from is not None:
            query = query.where(Operation.operation_date >= filters.date_from)
        if filters.date_to is not None:
            query = query.where(Operation.operation_date <= filters.date_to)
        if filters.search:
            query = query.where(Operation.description.ilike(f"%{filters.search}%"))
        if filters.account_id is not None:
            query = query.join(MoneyEntry).where(
                MoneyEntry.workspace_id == Operation.workspace_id,
                MoneyEntry.account_id == filters.account_id,
            )
        return query
