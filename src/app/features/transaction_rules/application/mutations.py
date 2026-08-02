from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
    UpdateTransactionRuleCommand,
)
from app.features.transaction_rules.application.directory import (
    category_reference,
    property_reference,
    transaction_rule_summary,
)
from app.features.transaction_rules.application.fixture_seeding import (
    DefaultMerchantRuleSeeder,
)
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.transaction_rules.errors import TransactionRuleNotFoundError
from app.features.transaction_rules.repository import TransactionRuleRepository
from app.features.transaction_rules.schemas import (
    TransactionRuleReferencesDto,
    TransactionRuleSummaryDto,
)
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


@dataclass(frozen=True)
class TransactionRuleEditResult:
    item: TransactionRuleSummaryDto
    references: TransactionRuleReferencesDto


@dataclass(frozen=True)
class TransactionRuleLifecycleImpact:
    future_matching_changed: bool
    existing_suggestions_changed: bool
    existing_suggestion_count: int


@dataclass(frozen=True)
class TransactionRuleLifecycleResult:
    item: TransactionRuleSummaryDto
    impact: TransactionRuleLifecycleImpact


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

    async def get_for_edit(
        self,
        *,
        context: WorkspaceContext,
        rule_id: UUID,
    ) -> TransactionRuleEditResult:
        rule = await self._rules.get_for_workspace(context.workspace.id, rule_id)
        if rule is None:
            raise TransactionRuleNotFoundError("Правило не найдено.")
        return await self._edit_result(context=context, rule_id=rule.id)

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateTransactionRuleCommand,
    ) -> TransactionRuleSummaryDto:
        updated = await self._management.update_rule(context=context, command=command)
        committed = await self._rules.get_for_workspace(context.workspace.id, updated.id)
        if committed is None:
            raise TransactionRuleNotFoundError("Правило не найдено.")
        direct_count = await self._rules.count_direct_raw_suggestions(
            workspace_id=context.workspace.id,
            rule_id=committed.id,
        )
        return transaction_rule_summary(
            committed,
            direct_raw_suggestion_count=direct_count,
            can_write=True,
        )

    async def set_active(
        self,
        *,
        context: WorkspaceContext,
        rule_id: UUID,
        is_active: bool,
        expected_active: bool,
        expected_updated_at: datetime,
    ) -> TransactionRuleLifecycleResult:
        changed = await self._management.set_rule_active(
            workspace_id=context.workspace.id,
            rule_id=rule_id,
            is_active=is_active,
            expected_active=expected_active,
            expected_updated_at=expected_updated_at,
        )
        committed = await self._rules.get_for_workspace(context.workspace.id, changed.id)
        if committed is None:
            raise TransactionRuleNotFoundError("Правило не найдено.")
        direct_count = await self._rules.count_direct_raw_suggestions(
            workspace_id=context.workspace.id,
            rule_id=committed.id,
        )
        return TransactionRuleLifecycleResult(
            item=transaction_rule_summary(
                committed,
                direct_raw_suggestion_count=direct_count,
                can_write=True,
            ),
            impact=TransactionRuleLifecycleImpact(
                future_matching_changed=True,
                existing_suggestions_changed=False,
                existing_suggestion_count=direct_count,
            ),
        )

    async def _edit_result(
        self,
        *,
        context: WorkspaceContext,
        rule_id: UUID,
    ) -> TransactionRuleEditResult:
        rule = await self._rules.get_for_workspace(context.workspace.id, rule_id)
        if rule is None:
            raise TransactionRuleNotFoundError("Правило не найдено.")
        category_ids = {rule.category_id} if rule.category_id is not None else set()
        property_ids = {rule.property_id} if rule.property_id is not None else set()
        categories = await self._rules.list_directory_categories(
            workspace_id=context.workspace.id,
            current_ids=category_ids,
        )
        properties = await self._rules.list_directory_properties(
            workspace_id=context.workspace.id,
            current_ids=property_ids,
        )
        direct_count = await self._rules.count_direct_raw_suggestions(
            workspace_id=context.workspace.id,
            rule_id=rule.id,
        )
        return TransactionRuleEditResult(
            item=transaction_rule_summary(
                rule,
                direct_raw_suggestion_count=direct_count,
                can_write=True,
            ),
            references=TransactionRuleReferencesDto(
                categories=[category_reference(item) for item in categories],
                properties=[property_reference(item) for item in properties],
            ),
        )
