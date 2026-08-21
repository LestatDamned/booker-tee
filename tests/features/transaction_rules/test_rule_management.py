from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, create_autospec
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
    TransactionRuleTargetResolver,
)
from app.features.transaction_rules.errors import (
    TransactionRuleDeleteBlockedError,
    TransactionRuleDeleteConflictError,
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
from app.features.transaction_rules.repository import TransactionRuleRepository


async def test_caller_owned_create_flushes_distinct_rules_without_commit() -> None:
    session = SimpleNamespace(
        commit=AsyncMock(),
        rollback=AsyncMock(),
        refresh=AsyncMock(),
    )
    repository = create_autospec(TransactionRuleRepository, instance=True)
    repository.create.side_effect = lambda rule: rule
    targets = create_autospec(TransactionRuleTargetResolver, instance=True)
    targets.resolve_for_create.return_value = ResolvedTransactionRuleTargets(None, None, None)
    service = TransactionRuleManagementUseCase(cast(AsyncSession, session))
    service.rules = repository
    service.targets = targets
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


async def test_update_rejects_stale_snapshot_before_resolving_targets() -> None:
    rule, service, session, _repository, targets = management_service(is_active=True)

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


async def test_update_preserves_fields_outside_the_command() -> None:
    rule, service, session, _repository, _targets = management_service(is_active=True)
    original_account_id = rule.account_id
    original_description = rule.auto_description
    original_affects_profit = rule.affects_profit

    updated = await service.update_rule(
        context=workspace_context(rule.workspace_id),
        command=update_command(rule, expected_updated_at=rule.updated_at),
    )

    assert updated is rule
    assert rule.account_id == original_account_id
    assert rule.auto_description == original_description
    assert rule.affects_profit == original_affects_profit
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(rule)


@pytest.mark.parametrize(
    ("expected_active", "updated_at_delta"),
    [
        pytest.param(False, timedelta(0), id="wrong-state"),
        pytest.param(True, timedelta(seconds=-1), id="stale-snapshot"),
    ],
)
async def test_lifecycle_rejects_conflicting_snapshot(
    expected_active: bool,
    updated_at_delta: timedelta,
) -> None:
    rule, service, session, _repository, _targets = management_service(is_active=True)

    with pytest.raises(TransactionRuleLifecycleConflictError):
        await service.set_rule_active(
            workspace_id=rule.workspace_id,
            rule_id=rule.id,
            is_active=False,
            expected_active=expected_active,
            expected_updated_at=rule.updated_at + updated_at_delta,
        )

    assert rule.is_active is True
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


async def test_lifecycle_masks_rule_outside_workspace_as_not_found() -> None:
    rule, service, session, repository, _targets = management_service(is_active=True)
    repository.get_for_workspace_for_update.return_value = None

    with pytest.raises(TransactionRuleNotFoundError):
        await service.set_rule_active(
            workspace_id=uuid4(),
            rule_id=rule.id,
            is_active=False,
        )

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


@pytest.mark.parametrize(
    ("initial_active", "target_active"),
    [
        pytest.param(True, False, id="disable"),
        pytest.param(False, True, id="enable"),
    ],
)
async def test_lifecycle_revalidates_targets_only_when_enabling(
    initial_active: bool,
    target_active: bool,
) -> None:
    rule, service, session, _repository, targets = management_service(is_active=initial_active)

    changed = await service.set_rule_active(
        workspace_id=rule.workspace_id,
        rule_id=rule.id,
        is_active=target_active,
        expected_active=initial_active,
        expected_updated_at=rule.updated_at,
    )

    assert changed.is_active is target_active
    if target_active:
        targets.validate_for_activation.assert_awaited_once_with(
            workspace_id=rule.workspace_id,
            rule=rule,
        )
    else:
        targets.validate_for_activation.assert_not_awaited()
    session.commit.assert_awaited_once()


@pytest.mark.parametrize(
    ("is_active", "suggestion_count", "dependency_field", "expected_value"),
    [
        pytest.param(True, 0, "is_active", True, id="active-rule"),
        pytest.param(False, 3, "raw_suggestion_count", 3, id="import-history"),
    ],
)
async def test_delete_blocks_rules_with_dependencies(
    is_active: bool,
    suggestion_count: int,
    dependency_field: str,
    expected_value: bool | int,
) -> None:
    rule, service, session, repository, _targets = management_service(is_active=is_active)
    repository.count_direct_raw_suggestions.return_value = suggestion_count

    with pytest.raises(TransactionRuleDeleteBlockedError) as blocked:
        await service.delete_rule(workspace_id=rule.workspace_id, rule_id=rule.id)

    assert getattr(blocked.value.dependencies, dependency_field) == expected_value
    repository.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


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


async def test_delete_rejects_stale_state_before_dependency_check() -> None:
    rule, service, session, repository, _targets = management_service(is_active=False)

    with pytest.raises(TransactionRuleDeleteConflictError):
        await service.delete_rule(
            workspace_id=rule.workspace_id,
            rule_id=rule.id,
            expected_active=True,
            expected_updated_at=rule.updated_at,
        )

    repository.count_direct_raw_suggestions.assert_not_awaited()
    repository.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


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
    repository = create_autospec(TransactionRuleRepository, instance=True)
    repository.get_for_workspace_for_update.return_value = rule
    repository.count_direct_raw_suggestions.return_value = 0
    targets = create_autospec(TransactionRuleTargetResolver, instance=True)
    targets.resolve_for_update.return_value = ResolvedTransactionRuleTargets(None, None, None)
    service = TransactionRuleManagementUseCase(cast(AsyncSession, session))
    service.rules = repository
    service.targets = targets
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
