from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.transaction_rules.models import TransactionRule
from app.features.transaction_rules.repository import TransactionRuleRepository


class TransactionRuleQueryUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.rules = TransactionRuleRepository(session)

    async def list_rules(self, workspace_id: UUID) -> list[TransactionRule]:
        return await self.rules.list_for_workspace(workspace_id)

    async def get_rule(self, *, workspace_id: UUID, rule_id: UUID) -> TransactionRule | None:
        return await self.rules.get_for_workspace(workspace_id, rule_id)
