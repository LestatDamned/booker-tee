from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.transaction_rules.models import TransactionRule


class TransactionRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_workspace(self, workspace_id: UUID) -> list[TransactionRule]:
        result = await self.session.execute(
            select(TransactionRule)
            .options(
                selectinload(TransactionRule.category),
                selectinload(TransactionRule.property),
                selectinload(TransactionRule.account),
            )
            .where(TransactionRule.workspace_id == workspace_id)
            .order_by(TransactionRule.priority, TransactionRule.name)
        )
        return list(result.scalars().all())

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[TransactionRule]:
        result = await self.session.execute(
            select(TransactionRule)
            .where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.is_active.is_(True),
            )
            .order_by(TransactionRule.priority, TransactionRule.created_at)
        )
        return list(result.scalars().all())

    async def get_for_workspace(
        self,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> TransactionRule | None:
        result = await self.session.execute(
            select(TransactionRule).where(
                TransactionRule.id == rule_id,
                TransactionRule.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_existing(
        self,
        *,
        workspace_id: UUID,
        pattern: str,
        category_id: UUID | None,
    ) -> TransactionRule | None:
        result = await self.session.execute(
            select(TransactionRule).where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.pattern == pattern,
                TransactionRule.category_id == category_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, rule: TransactionRule) -> TransactionRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def delete(self, rule: TransactionRule) -> None:
        await self.session.delete(rule)
        await self.session.flush()
