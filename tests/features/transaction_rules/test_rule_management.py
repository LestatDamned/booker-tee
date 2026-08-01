from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
    UpdateTransactionRuleCommand,
)
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.transaction_rules.application.target_resolution import (
    ResolvedTransactionRuleTargets,
)
from app.features.transaction_rules.errors import (
    TransactionRuleDeleteBlockedError,
    TransactionRuleLifecycleConflictError,
    TransactionRuleNotFoundError,
    TransactionRuleUpdateConflictError,
)
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)


@pytest.mark.asyncio
async def test_caller_owned_create_flushes_distinct_rules_without_commit() -> None:
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        refresh=AsyncMock(),
    )
    repository = SimpleNamespace(create=AsyncMock(side_effect=lambda rule: rule))
    targets = SimpleNamespace(
        resolve_for_create=AsyncMock(return_value=ResolvedTransactionRuleTargets(None, None, None))
    )
    service = TransactionRuleManagementUseCase(cast(AsyncSession, session))
    service.rules = cast(Any, repository)
    service.targets = cast(Any, targets)
    context = workspace_context(uuid4())
    command = CreateTransactionRuleCommand(
        name="OZON",
        pattern="OZON",
        match_type=TransactionRuleMatchType.CONTAINS,
        category_id=None,
        property_id=None,
        target_operation_type=None,
        direction=MoneyDirection.OUTFLOW,
    )

    first = await service.create_rule_in_transaction(context=context, command=command)
    second = await service.create_rule_in_transaction(context=context, command=command)

    assert first is not second
    assert repository.create.await_count == 2
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_rejects_stale_snapshot_and_preserves_dormant_fields() -> None:
    rule, service, session, repository, targets = management_service(is_active=True)
    original_account_id = rule.account_id
    original_description = rule.auto_description
    original_affects_profit = rule.affects_profit

    with pytest.raises(TransactionRuleUpdateConflictError):
        await service.update_rule(
            context=workspace_context(rule.workspace_id),
            command=update_command(
                rule,
                expected_updated_at=rule.updated_at - timedelta(seconds=1),
            ),
        )

    session.commit.assert_not_awaited()
    targets.resolve_for_update.assert_not_awaited()
    session.rollback.assert_awaited_once()

    session.rollback.reset_mock()
    updated = await service.update_rule(
        context=workspace_context(rule.workspace_id),
        command=update_command(rule, expected_updated_at=rule.updated_at),
    )

    assert updated is rule
    assert rule.account_id == original_account_id
    assert rule.auto_description == original_description
    assert rule.affects_profit == original_affects_profit
    repository.delete.assert_not_awaited()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(rule)


@pytest.mark.asyncio
async def test_lifecycle_rejects_wrong_state_stale_and_missing_rule() -> None:
    rule, service, session, repository, _targets = management_service(is_active=True)

    with pytest.raises(TransactionRuleLifecycleConflictError):
        await service.set_rule_active(
            workspace_id=rule.workspace_id,
            rule_id=rule.id,
            is_active=False,
            expected_active=False,
            expected_updated_at=rule.updated_at,
        )
    with pytest.raises(TransactionRuleLifecycleConflictError):
        await service.set_rule_active(
            workspace_id=rule.workspace_id,
            rule_id=rule.id,
            is_active=False,
            expected_active=True,
            expected_updated_at=rule.updated_at - timedelta(seconds=1),
        )

    repository.get_for_workspace_for_update.return_value = None
    with pytest.raises(TransactionRuleNotFoundError):
        await service.set_rule_active(
            workspace_id=uuid4(),
            rule_id=rule.id,
            is_active=False,
        )
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_enable_revalidates_targets_and_disable_does_not_rewrite_suggestions() -> None:
    rule, service, session, _repository, targets = management_service(is_active=True)

    disabled = await service.set_rule_active(
        workspace_id=rule.workspace_id,
        rule_id=rule.id,
        is_active=False,
        expected_active=True,
        expected_updated_at=rule.updated_at,
    )

    assert disabled.is_active is False
    targets.validate_for_activation.assert_not_awaited()

    enabled = await service.set_rule_active(
        workspace_id=rule.workspace_id,
        rule_id=rule.id,
        is_active=True,
        expected_active=False,
        expected_updated_at=rule.updated_at,
    )

    assert enabled.is_active is True
    targets.validate_for_activation.assert_awaited_once_with(
        workspace_id=rule.workspace_id,
        rule=rule,
    )
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_delete_blocks_active_and_referenced_rules() -> None:
    rule, service, session, repository, _targets = management_service(is_active=True)

    with pytest.raises(TransactionRuleDeleteBlockedError) as active_blocked:
        await service.delete_rule(workspace_id=rule.workspace_id, rule_id=rule.id)
    assert active_blocked.value.dependencies.is_active is True
    repository.delete.assert_not_awaited()

    rule.is_active = False
    repository.count_direct_raw_suggestions.return_value = 3
    with pytest.raises(TransactionRuleDeleteBlockedError) as referenced_blocked:
        await service.delete_rule(workspace_id=rule.workspace_id, rule_id=rule.id)
    assert referenced_blocked.value.dependencies.raw_suggestion_count == 3
    repository.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_removes_only_unused_disabled_workspace_rule() -> None:
    rule, service, session, repository, _targets = management_service(is_active=False)

    deleted = await service.delete_rule(
        workspace_id=rule.workspace_id,
        rule_id=rule.id,
        expected_active=False,
        expected_updated_at=rule.updated_at,
    )

    assert deleted.id == rule.id
    assert deleted.name == rule.name
    repository.delete.assert_awaited_once_with(rule)
    session.commit.assert_awaited_once()


def management_service(
    *,
    is_active: bool,
) -> tuple[TransactionRule, TransactionRuleManagementUseCase, Any, Any, Any]:
    updated_at = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)
    rule = TransactionRule(
        id=uuid4(),
        workspace_id=uuid4(),
        name="OZON -> Маркетплейсы",
        is_active=is_active,
        pattern="OZON",
        match_type=TransactionRuleMatchType.CONTAINS,
        application_mode=TransactionRuleApplicationMode.SUGGEST,
        direction=MoneyDirection.OUTFLOW,
        account_id=uuid4(),
        auto_description="dormant",
        affects_profit=True,
        updated_at=updated_at,
    )
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        refresh=AsyncMock(),
    )
    repository = SimpleNamespace(
        get_for_workspace_for_update=AsyncMock(return_value=rule),
        count_direct_raw_suggestions=AsyncMock(return_value=0),
        delete=AsyncMock(),
    )
    targets = SimpleNamespace(
        resolve_for_update=AsyncMock(return_value=ResolvedTransactionRuleTargets(None, None, None)),
        validate_for_activation=AsyncMock(),
    )
    service = TransactionRuleManagementUseCase(cast(AsyncSession, session))
    service.rules = cast(Any, repository)
    service.targets = cast(Any, targets)
    return rule, service, session, repository, targets


def update_command(
    rule: TransactionRule,
    *,
    expected_updated_at: datetime,
) -> UpdateTransactionRuleCommand:
    return UpdateTransactionRuleCommand(
        rule_id=rule.id,
        name=rule.name,
        pattern=rule.pattern,
        match_type=rule.match_type,
        category_id=None,
        property_id=None,
        target_operation_type=None,
        direction=rule.direction,
        application_mode=rule.application_mode,
        expected_updated_at=expected_updated_at,
    )


def workspace_context(workspace_id):
    return SimpleNamespace(
        workspace=SimpleNamespace(id=workspace_id),
        user=SimpleNamespace(id=uuid4()),
    )
