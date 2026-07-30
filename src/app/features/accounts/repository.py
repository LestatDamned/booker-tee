from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account, AccountType
from app.features.ledger.models import MoneyEntry, Operation, OperationStatus


@dataclass(frozen=True)
class AccountDirectoryRow:
    id: UUID
    name: str
    account_type: AccountType
    currency: str
    initial_balance: Decimal
    is_active: bool
    updated_at: datetime
    confirmed_entry_total: Decimal
    confirmed_movement_count: int


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_workspace(self, workspace_id: UUID) -> list[Account]:
        result = await self.session.execute(
            select(Account)
            .where(Account.workspace_id == workspace_id)
            .order_by(Account.is_active.desc(), Account.created_at)
        )
        return list(result.scalars().all())

    async def list_directory_rows(self, workspace_id: UUID) -> list[AccountDirectoryRow]:
        confirmed_entry_total = func.coalesce(
            func.sum(MoneyEntry.amount).filter(Operation.status == OperationStatus.CONFIRMED),
            Decimal("0.00"),
        )
        confirmed_movement_count = func.count(MoneyEntry.id).filter(
            Operation.status == OperationStatus.CONFIRMED
        )
        result = await self.session.execute(
            select(
                Account,
                confirmed_entry_total,
                confirmed_movement_count,
            )
            .outerjoin(
                MoneyEntry,
                and_(
                    MoneyEntry.account_id == Account.id,
                    MoneyEntry.workspace_id == workspace_id,
                ),
            )
            .outerjoin(
                Operation,
                and_(
                    Operation.id == MoneyEntry.operation_id,
                    Operation.workspace_id == workspace_id,
                ),
            )
            .where(Account.workspace_id == workspace_id)
            .group_by(Account.id)
            .order_by(Account.is_active.desc(), Account.created_at)
        )
        return [
            AccountDirectoryRow(
                id=account.id,
                name=account.name,
                account_type=account.type,
                currency=account.currency,
                initial_balance=account.initial_balance,
                is_active=account.is_active,
                updated_at=account.updated_at,
                confirmed_entry_total=entry_total,
                confirmed_movement_count=movement_count,
            )
            for account, entry_total, movement_count in result.all()
        ]

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Account]:
        result = await self.session.execute(
            select(Account)
            .where(Account.workspace_id == workspace_id, Account.is_active.is_(True))
            .order_by(Account.created_at)
        )
        return list(result.scalars().all())

    async def get_for_workspace(self, workspace_id: UUID, account_id: UUID) -> Account | None:
        result = await self.session.execute(
            select(Account).where(
                Account.id == account_id,
                Account.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, account: Account) -> Account:
        self.session.add(account)
        await self.session.flush()
        return account
