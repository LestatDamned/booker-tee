from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account


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
