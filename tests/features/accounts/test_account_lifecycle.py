from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.features.accounts.models import Account
from app.features.accounts.repository import AccountRepository
from app.features.accounts.service import (
    AccountLifecycleConflictError,
    AccountService,
)


class AccountRepositoryStub:
    def __init__(self, account: Account) -> None:
        self.account = account

    async def get_for_workspace(self, workspace_id, account_id):  # noqa: ANN001
        if self.account.workspace_id == workspace_id and self.account.id == account_id:
            return self.account
        return None


async def test_account_lifecycle_checks_expected_snapshot_before_commit() -> None:
    workspace_id = uuid4()
    updated_at = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Основной",
        is_active=True,
        updated_at=updated_at,
    )
    session = AsyncMock()
    service = AccountService(session)
    service.accounts = cast(AccountRepository, AccountRepositoryStub(account))

    result = await service.set_active(
        workspace_id=workspace_id,
        account_id=account.id,
        is_active=False,
        expected_active=True,
        expected_updated_at=updated_at,
    )

    assert result.is_active is False
    assert result.archived_at is not None
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(account)


async def test_account_lifecycle_rejects_stale_timestamp_without_commit() -> None:
    workspace_id = uuid4()
    updated_at = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Основной",
        is_active=True,
        updated_at=updated_at,
    )
    session = AsyncMock()
    service = AccountService(session)
    service.accounts = cast(AccountRepository, AccountRepositoryStub(account))

    with pytest.raises(AccountLifecycleConflictError):
        await service.set_active(
            workspace_id=workspace_id,
            account_id=account.id,
            is_active=False,
            expected_active=True,
            expected_updated_at=updated_at - timedelta(seconds=1),
        )

    session.commit.assert_not_awaited()
