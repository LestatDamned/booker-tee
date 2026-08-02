from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
)
from app.features.transaction_rules.application.directory import transaction_rule_summary
from app.features.transaction_rules.application.fixture_seeding import (
    DefaultMerchantRuleSeeder,
)
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.transaction_rules.repository import TransactionRuleRepository
from app.features.transaction_rules.schemas import TransactionRuleSummaryDto
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class TransactionRuleCreateResult:
    item: TransactionRuleSummaryDto
    replayed: bool


@dataclass(frozen=True)
class TransactionRuleSeedDefaultsResult:
    created_rules: int
    existing_rules: int
    created_categories: int


class TransactionRuleMutationService:
    def __init__(self, session: AsyncSession) -> None:
        self._management = TransactionRuleManagementUseCase(session)
        self._rules = TransactionRuleRepository(session)
        self._seeder = DefaultMerchantRuleSeeder(session)

    async def create(
        self,
        *,
        context: WorkspaceContext,
        command: CreateTransactionRuleCommand,
        idempotency_key: UUID,
    ) -> TransactionRuleCreateResult:
        created = await self._management.create_rule_idempotently(
            context=context,
            command=command,
            idempotency_key=idempotency_key,
        )
        direct_count = await self._rules.count_direct_raw_suggestions(
            workspace_id=context.workspace.id,
            rule_id=created.rule.id,
        )
        return TransactionRuleCreateResult(
            item=transaction_rule_summary(
                created.rule,
                direct_raw_suggestion_count=direct_count,
                can_write=True,
            ),
            replayed=created.replayed,
        )

    async def seed_defaults(
        self,
        *,
        context: WorkspaceContext,
    ) -> TransactionRuleSeedDefaultsResult:
        seeded = await self._seeder.seed(context)
        return TransactionRuleSeedDefaultsResult(
            created_rules=seeded.created_rule_count,
            existing_rules=seeded.existing_rule_count,
            created_categories=seeded.created_category_count,
        )
