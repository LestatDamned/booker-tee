from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.imports.models import RawTransaction
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

    async def list_manual_operations_for_workspace(self, workspace_id: UUID) -> list[Operation]:
        result = await self.session.execute(
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
            .order_by(Operation.operation_date.desc(), Operation.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_manual_transfer_candidates_for_raw_transaction(
        self,
        *,
        workspace_id: UUID,
        raw_transaction: RawTransaction,
        day_window: int = 3,
    ) -> list[Operation]:
        if (
            raw_transaction.amount is None
            or raw_transaction.currency is None
            or raw_transaction.operation_date is None
            or raw_transaction.account_id is None
        ):
            return []

        result = await self.session.execute(
            select(Operation)
            .join(MoneyEntry)
            .options(
                selectinload(Operation.raw_transactions),
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
                MoneyEntry.account_id == raw_transaction.account_id,
                MoneyEntry.amount == raw_transaction.amount,
                MoneyEntry.currency == raw_transaction.currency,
            )
            .order_by(Operation.operation_date, Operation.created_at)
        )
        return [
            operation
            for operation in result.unique().scalars().all()
            if not any(
                linked_raw.account_id == raw_transaction.account_id
                for linked_raw in operation.raw_transactions
            )
        ]

    async def delete_operation(self, operation: Operation) -> None:
        await self.session.delete(operation)
        await self.session.flush()

    async def list_account_entries(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
    ) -> list[MoneyEntry]:
        result = await self.session.execute(
            select(MoneyEntry)
            .options(
                selectinload(MoneyEntry.account),
                selectinload(MoneyEntry.operation).selectinload(Operation.category),
                selectinload(MoneyEntry.operation).selectinload(Operation.property),
                selectinload(MoneyEntry.operation)
                .selectinload(Operation.money_entries)
                .selectinload(MoneyEntry.account),
            )
            .join(Operation)
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == account_id,
                Operation.status == OperationStatus.CONFIRMED,
            )
            .order_by(Operation.operation_date.desc(), MoneyEntry.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_confirmed_account_entries_total(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
    ) -> Decimal:
        result = await self.session.execute(
            select(func.coalesce(func.sum(MoneyEntry.amount), Decimal("0.00")))
            .join(Operation)
            .where(
                MoneyEntry.workspace_id == workspace_id,
                MoneyEntry.account_id == account_id,
                Operation.status == OperationStatus.CONFIRMED,
            )
        )
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
