from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.imports.models import RawTransaction
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

    async def list_for_category(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
    ) -> list[TransactionRule]:
        result = await self.session.execute(
            select(TransactionRule)
            .options(
                selectinload(TransactionRule.category),
                selectinload(TransactionRule.property),
                selectinload(TransactionRule.account),
            )
            .where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.category_id == category_id,
            )
            .order_by(TransactionRule.priority, TransactionRule.name)
        )
        return list(result.scalars().all())

    async def list_category_preview(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        limit: int,
    ) -> list[TransactionRule]:
        result = await self.session.execute(
            select(TransactionRule)
            .where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.category_id == category_id,
            )
            .order_by(TransactionRule.priority, TransactionRule.name)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_category_rules(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
    ) -> tuple[int, int]:
        active_count = func.count(TransactionRule.id).filter(TransactionRule.is_active.is_(True))
        result = await self.session.execute(
            select(func.count(TransactionRule.id), active_count).where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.category_id == category_id,
            )
        )
        row = result.one()
        return row[0], row[1]

    async def get_for_workspace(
        self,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> TransactionRule | None:
        result = await self.session.execute(
            select(TransactionRule)
            .options(
                selectinload(TransactionRule.category),
                selectinload(TransactionRule.property),
                selectinload(TransactionRule.account),
            )
            .where(
                TransactionRule.id == rule_id,
                TransactionRule.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_workspace_for_update(
        self,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> TransactionRule | None:
        result = await self.session.execute(
            select(TransactionRule)
            .where(
                TransactionRule.id == rule_id,
                TransactionRule.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(self, rule: TransactionRule) -> TransactionRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def count_direct_raw_suggestions(
        self,
        *,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count(RawTransaction.id)).where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.suggested_by_rule_id == rule_id,
            )
        )
        return result.scalar_one()

    async def delete(self, rule: TransactionRule) -> None:
        await self.session.delete(rule)
        await self.session.flush()
