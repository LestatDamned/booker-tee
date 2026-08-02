from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import RawTransaction
from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
    UpdateTransactionRuleCommand,
)
from app.features.transaction_rules.application.target_resolution import (
    TransactionRuleTargetResolver,
)
from app.features.transaction_rules.domain.matching import (
    direction_for_raw_transaction,
    operation_type_for_raw_transaction,
)
from app.features.transaction_rules.domain.patterns import infer_rule_pattern
from app.features.transaction_rules.domain.validation import validate_transaction_rule_fields
from app.features.transaction_rules.errors import (
    TransactionRuleCreateReplayConflictError,
    TransactionRuleDeleteBlockedError,
    TransactionRuleDeleteDependencies,
    TransactionRuleLifecycleConflictError,
    TransactionRuleNotFoundError,
    TransactionRuleUpdateConflictError,
)
from app.features.transaction_rules.models import (
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.repository import TransactionRuleRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class DeletedTransactionRule:
    id: UUID
    name: str


@dataclass(frozen=True)
class CreatedTransactionRule:
    rule: TransactionRule
    replayed: bool


class TransactionRuleManagementUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rules = TransactionRuleRepository(session)
        self.targets = TransactionRuleTargetResolver(session)

    async def create_rule(
        self,
        *,
        context: WorkspaceContext,
        command: CreateTransactionRuleCommand,
    ) -> TransactionRule:
        try:
            rule = await self.create_rule_in_transaction(context=context, command=command)
            await self.session.commit()
            await self.session.refresh(rule)
            return rule
        except Exception:
            await self.session.rollback()
            raise

    async def create_rule_idempotently(
        self,
        *,
        context: WorkspaceContext,
        command: CreateTransactionRuleCommand,
        idempotency_key: UUID,
    ) -> CreatedTransactionRule:
        rule_id = uuid5(
            context.workspace.id,
            f"transaction-rule-create:{idempotency_key}",
        )
        existing = await self.rules.get_for_workspace(context.workspace.id, rule_id)
        if existing is not None:
            self._validate_create_replay(existing, command)
            return CreatedTransactionRule(rule=existing, replayed=True)
        try:
            rule = await self.create_rule_in_transaction(
                context=context,
                command=command,
                rule_id=rule_id,
            )
            await self.session.commit()
            created = await self.rules.get_for_workspace(context.workspace.id, rule.id)
            if created is None:
                raise TransactionRuleNotFoundError("Created rule is not available.")
            return CreatedTransactionRule(rule=created, replayed=False)
        except IntegrityError:
            await self.session.rollback()
            existing = await self.rules.get_for_workspace(context.workspace.id, rule_id)
            if existing is None:
                raise
            self._validate_create_replay(existing, command)
            return CreatedTransactionRule(rule=existing, replayed=True)
        except Exception:
            await self.session.rollback()
            raise

    async def create_rule_in_transaction(
        self,
        *,
        context: WorkspaceContext,
        command: CreateTransactionRuleCommand,
        rule_id: UUID | None = None,
    ) -> TransactionRule:
        """Create and flush a rule without taking ownership of the transaction."""
        targets = await self.targets.resolve_for_create(
            workspace_id=context.workspace.id,
            category_id=command.category_id,
            property_id=command.property_id,
            account_id=command.account_id,
        )
        fields = validate_transaction_rule_fields(
            name=command.name,
            pattern=command.pattern,
            match_type=command.match_type,
            category_name=targets.category.name if targets.category else None,
            target_operation_type=command.target_operation_type,
            amount_min=command.amount_min,
            amount_max=command.amount_max,
            auto_description=command.auto_description,
        )
        rule = TransactionRule(
            workspace_id=context.workspace.id,
            name=fields.name,
            match_type=command.match_type,
            pattern=fields.pattern,
            application_mode=command.application_mode,
            account_id=targets.account.id if targets.account else None,
            amount_min=fields.amount_min,
            amount_max=fields.amount_max,
            direction=command.direction,
            target_operation_type=command.target_operation_type,
            category_id=targets.category.id if targets.category else None,
            property_id=targets.property.id if targets.property else None,
            auto_description=fields.auto_description,
            affects_profit=command.affects_profit,
            created_by_user_id=context.user.id,
        )
        if rule_id is not None:
            rule.id = rule_id
        return await self.rules.create(rule)

    async def update_rule(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateTransactionRuleCommand,
    ) -> TransactionRule:
        try:
            rule = await self._get_rule_for_update(context.workspace.id, command.rule_id)
            if (
                command.expected_updated_at is not None
                and rule.updated_at != command.expected_updated_at
            ):
                raise TransactionRuleUpdateConflictError("Правило уже изменилось в другом окне.")
            targets = await self.targets.resolve_for_update(
                workspace_id=context.workspace.id,
                rule=rule,
                category_id=command.category_id,
                property_id=command.property_id,
            )
            fields = validate_transaction_rule_fields(
                name=command.name,
                pattern=command.pattern,
                match_type=command.match_type,
                category_name=targets.category.name if targets.category else None,
                target_operation_type=command.target_operation_type,
                amount_min=command.amount_min,
                amount_max=command.amount_max,
            )
            rule.name = fields.name
            rule.pattern = fields.pattern
            rule.match_type = command.match_type
            rule.category_id = targets.category.id if targets.category else None
            rule.property_id = targets.property.id if targets.property else None
            rule.target_operation_type = command.target_operation_type
            rule.direction = command.direction
            rule.application_mode = command.application_mode
            rule.amount_min = fields.amount_min
            rule.amount_max = fields.amount_max
            await self.session.commit()
            await self.session.refresh(rule)
            return rule
        except Exception:
            await self.session.rollback()
            raise

    async def set_rule_active(
        self,
        *,
        workspace_id: UUID,
        rule_id: UUID,
        is_active: bool,
        expected_active: bool | None = None,
        expected_updated_at: datetime | None = None,
    ) -> TransactionRule:
        try:
            rule = await self._get_rule_for_update(workspace_id, rule_id)
            if expected_active is not None and rule.is_active is not expected_active:
                raise TransactionRuleLifecycleConflictError("Состояние правила уже изменилось.")
            if expected_updated_at is not None and rule.updated_at != expected_updated_at:
                raise TransactionRuleLifecycleConflictError("Правило уже изменилось в другом окне.")
            if is_active:
                await self.targets.validate_for_activation(
                    workspace_id=workspace_id,
                    rule=rule,
                )
            rule.is_active = is_active
            await self.session.commit()
            await self.session.refresh(rule)
            return rule
        except Exception:
            await self.session.rollback()
            raise

    async def delete_rule(
        self,
        *,
        workspace_id: UUID,
        rule_id: UUID,
        expected_active: bool | None = None,
        expected_updated_at: datetime | None = None,
    ) -> DeletedTransactionRule:
        try:
            rule = await self._get_rule_for_update(workspace_id, rule_id)
            if expected_active is not None and rule.is_active is not expected_active:
                raise TransactionRuleLifecycleConflictError("Состояние правила уже изменилось.")
            if expected_updated_at is not None and rule.updated_at != expected_updated_at:
                raise TransactionRuleLifecycleConflictError("Правило уже изменилось в другом окне.")
            dependencies = TransactionRuleDeleteDependencies(
                is_active=rule.is_active,
                raw_suggestion_count=await self.rules.count_direct_raw_suggestions(
                    workspace_id=workspace_id,
                    rule_id=rule_id,
                ),
            )
            if dependencies.has_blockers:
                raise TransactionRuleDeleteBlockedError(dependencies)
            deleted = DeletedTransactionRule(id=rule.id, name=rule.name)
            await self.rules.delete(rule)
            await self.session.commit()
            return deleted
        except IntegrityError as exc:
            await self.session.rollback()
            raise TransactionRuleDeleteBlockedError(
                TransactionRuleDeleteDependencies(raw_suggestion_count=1)
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

    async def create_rule_from_raw_transaction(
        self,
        *,
        context: WorkspaceContext,
        raw_transaction: RawTransaction,
        category_id: UUID,
        property_id: UUID | None,
        pattern: str | None,
    ) -> TransactionRule:
        inferred_pattern = pattern or infer_rule_pattern(raw_transaction)
        return await self.create_rule_in_transaction(
            context=context,
            command=CreateTransactionRuleCommand(
                name=None,
                pattern=inferred_pattern,
                match_type=TransactionRuleMatchType.CONTAINS,
                category_id=category_id,
                property_id=property_id,
                target_operation_type=operation_type_for_raw_transaction(raw_transaction),
                direction=direction_for_raw_transaction(raw_transaction),
                application_mode=TransactionRuleApplicationMode.SUGGEST,
            ),
        )

    async def _get_rule_for_update(
        self,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> TransactionRule:
        rule = await self.rules.get_for_workspace_for_update(workspace_id, rule_id)
        if rule is None:
            raise TransactionRuleNotFoundError("Правило не найдено в этом workspace.")
        return rule

    @staticmethod
    def _validate_create_replay(
        rule: TransactionRule,
        command: CreateTransactionRuleCommand,
    ) -> None:
        fields = validate_transaction_rule_fields(
            name=command.name,
            pattern=command.pattern,
            match_type=command.match_type,
            category_name=rule.category.name if rule.category else None,
            target_operation_type=command.target_operation_type,
            amount_min=command.amount_min,
            amount_max=command.amount_max,
            auto_description=command.auto_description,
        )
        matches = (
            rule.name == fields.name
            and rule.pattern == fields.pattern
            and rule.match_type == command.match_type
            and rule.category_id == command.category_id
            and rule.property_id == command.property_id
            and rule.account_id == command.account_id
            and rule.target_operation_type == command.target_operation_type
            and rule.direction == command.direction
            and rule.application_mode == command.application_mode
            and rule.amount_min == fields.amount_min
            and rule.amount_max == fields.amount_max
            and rule.auto_description == fields.auto_description
            and rule.affects_profit is command.affects_profit
        )
        if not matches:
            raise TransactionRuleCreateReplayConflictError(
                "Idempotency key was reused with a different transaction rule."
            )
