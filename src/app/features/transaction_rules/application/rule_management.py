from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.service import CategoryError, CategoryService
from app.features.imports.repository import ImportRepository
from app.features.properties.service import PropertyError, PropertyService
from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
    UpdateTransactionRuleCommand,
)
from app.features.transaction_rules.domain.matching import (
    direction_for_raw_transaction,
    operation_type_for_raw_transaction,
)
from app.features.transaction_rules.domain.patterns import infer_rule_pattern
from app.features.transaction_rules.domain.text import (
    build_rule_name,
    clean_description,
    clean_rule_name,
    clean_rule_pattern,
)
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.transaction_rules.models import (
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.repository import TransactionRuleRepository
from app.features.workspaces.service import WorkspaceContext


class TransactionRuleManagementUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)
        self.rules = TransactionRuleRepository(session)

    async def create_rule(
        self,
        *,
        context: WorkspaceContext,
        command: CreateTransactionRuleCommand,
    ) -> TransactionRule:
        category, property_ = await self._resolve_targets(
            workspace_id=context.workspace.id,
            category_id=command.category_id,
            property_id=command.property_id,
        )
        cleaned_pattern = clean_rule_pattern(command.pattern)
        cleaned_name = clean_rule_name(command.name) or build_rule_name(
            pattern=cleaned_pattern,
            match_type=command.match_type,
            category_name=category.name if category else None,
            target_operation_type=command.target_operation_type,
        )
        existing = await self.rules.find_existing(
            workspace_id=context.workspace.id,
            pattern=cleaned_pattern,
            category_id=category.id if category else None,
        )
        if existing is not None:
            return existing

        rule = await self.rules.create(
            TransactionRule(
                workspace_id=context.workspace.id,
                name=cleaned_name,
                match_type=command.match_type,
                pattern=cleaned_pattern,
                application_mode=command.application_mode,
                account_id=command.account_id,
                amount_min=command.amount_min,
                amount_max=command.amount_max,
                direction=command.direction,
                target_operation_type=command.target_operation_type,
                category_id=category.id if category else None,
                property_id=property_.id if property_ else None,
                auto_description=clean_description(command.auto_description),
                affects_profit=command.affects_profit,
                created_by_user_id=context.user.id,
            )
        )
        await self.session.commit()
        return rule

    async def update_rule(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateTransactionRuleCommand,
    ) -> TransactionRule:
        rule = await self.rules.get_for_workspace(context.workspace.id, command.rule_id)
        if rule is None:
            raise TransactionRuleError("Правило не найдено в этом workspace.")
        category, property_ = await self._resolve_targets(
            workspace_id=context.workspace.id,
            category_id=command.category_id,
            property_id=command.property_id,
        )
        cleaned_pattern = clean_rule_pattern(command.pattern)
        rule.name = clean_rule_name(command.name) or build_rule_name(
            pattern=cleaned_pattern,
            match_type=command.match_type,
            category_name=category.name if category else None,
            target_operation_type=command.target_operation_type,
        )
        rule.pattern = cleaned_pattern
        rule.match_type = command.match_type
        rule.category_id = category.id if category else None
        rule.property_id = property_.id if property_ else None
        rule.target_operation_type = command.target_operation_type
        rule.direction = command.direction
        rule.application_mode = command.application_mode
        rule.amount_min = command.amount_min
        rule.amount_max = command.amount_max
        await self.session.commit()
        return rule

    async def set_rule_active(
        self,
        *,
        workspace_id: UUID,
        rule_id: UUID,
        is_active: bool,
    ) -> TransactionRule:
        rule = await self.rules.get_for_workspace(workspace_id, rule_id)
        if rule is None:
            raise TransactionRuleError("Правило не найдено в этом workspace.")
        rule.is_active = is_active
        await self.session.commit()
        return rule

    async def delete_rule(self, *, workspace_id: UUID, rule_id: UUID) -> None:
        rule = await self.rules.get_for_workspace(workspace_id, rule_id)
        if rule is None:
            raise TransactionRuleError("Правило не найдено в этом workspace.")
        await self.rules.delete(rule)
        await self.session.commit()

    async def create_rule_from_raw_confirmation(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        category_id: UUID,
        property_id: UUID | None,
        pattern: str | None,
    ) -> TransactionRule:
        raw_transaction = await self.imports.get_raw_transaction_for_workspace(
            context.workspace.id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise TransactionRuleError("Raw transaction row was not found.")
        inferred_pattern = pattern or infer_rule_pattern(raw_transaction)
        return await self.create_rule(
            context=context,
            command=CreateTransactionRuleCommand(
                name=f"{inferred_pattern} -> category",
                pattern=inferred_pattern,
                match_type=TransactionRuleMatchType.CONTAINS,
                category_id=category_id,
                property_id=property_id,
                target_operation_type=operation_type_for_raw_transaction(raw_transaction),
                direction=direction_for_raw_transaction(raw_transaction),
                application_mode=TransactionRuleApplicationMode.SUGGEST,
            ),
        )

    async def _resolve_targets(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID | None,
        property_id: UUID | None,
    ):
        try:
            category = await CategoryService(self.session).get_for_workspace(
                workspace_id,
                category_id,
            )
            property_ = await PropertyService(self.session).get_for_workspace(
                workspace_id,
                property_id,
            )
        except (CategoryError, PropertyError) as exc:
            raise TransactionRuleError(str(exc)) from exc
        return category, property_
