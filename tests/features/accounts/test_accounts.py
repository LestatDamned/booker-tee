from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.accounts.service import (
    AccountCurrencyConflictError,
    AccountError,
    AccountNotFoundError,
    AccountService,
    AccountUpdateConflictError,
    normalize_currency,
)


def test_normalize_currency_uppercases_three_letter_code() -> None:
    assert normalize_currency("rub") == "RUB"


def test_normalize_currency_rejects_invalid_code() -> None:
    with pytest.raises(AccountError):
        normalize_currency("rouble")


async def test_account_lookup_is_workspace_scoped() -> None:
    workspace_id = uuid4()
    account_id = uuid4()
    execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: None),
    )

    result = await AccountRepository(
        cast(AsyncSession, SimpleNamespace(execute=execute))
    ).get_for_workspace(workspace_id, account_id)

    assert result is None
    assert execute.await_args is not None
    compiled = execute.await_args.args[0].compile()
    sql = str(compiled)
    assert "accounts.id" in sql
    assert "accounts.workspace_id" in sql
    assert {workspace_id, account_id} <= set(compiled.params.values())


async def test_generic_account_service_rejects_debt_account_creation() -> None:
    service = account_service(existing_account(), has_entries=False)

    with pytest.raises(AccountError):
        await service.create(
            workspace_id=uuid4(),
            name="Ипотека",
            account_type=AccountType.DEBT,
            currency="RUB",
            initial_balance=Decimal("-100.00"),
        )


async def test_generic_account_service_rejects_debt_account_update() -> None:
    account = existing_account()
    account.type = AccountType.DEBT
    service = account_service(account, has_entries=False)

    with pytest.raises(AccountError):
        await service.update(
            workspace_id=account.workspace_id,
            account_id=account.id,
            name="Ипотека",
            account_type=AccountType.CARD,
            currency=account.currency,
            initial_balance=account.initial_balance,
        )


async def test_generic_account_service_rejects_debt_account_lifecycle_change() -> None:
    account = existing_account()
    account.type = AccountType.DEBT
    service = account_service(account, has_entries=False)

    with pytest.raises(AccountError):
        await service.set_active(
            workspace_id=account.workspace_id,
            account_id=account.id,
            is_active=False,
        )


async def test_update_rejects_currency_change_when_account_has_entries() -> None:
    account = existing_account()
    service = account_service(account, has_entries=True)

    with pytest.raises(AccountCurrencyConflictError):
        await service.update(
            workspace_id=account.workspace_id,
            account_id=account.id,
            name=account.name,
            account_type=account.type,
            currency="USD",
            initial_balance=account.initial_balance,
            expected_updated_at=account.updated_at,
        )

    assert account.currency == "RUB"


async def test_update_rejects_stale_write_before_mutating_account() -> None:
    account = existing_account()
    service = account_service(account, has_entries=False)

    with pytest.raises(AccountUpdateConflictError):
        await service.update(
            workspace_id=account.workspace_id,
            account_id=account.id,
            name="Новое имя",
            account_type=account.type,
            currency=account.currency,
            initial_balance=account.initial_balance,
            expected_updated_at=account.updated_at - timedelta(minutes=1),
        )

    assert account.name == "Основной"


async def test_update_rejects_foreign_workspace_before_mutating_account() -> None:
    account = existing_account()
    service = account_service(account, has_entries=False)

    with pytest.raises(AccountNotFoundError):
        await service.update(
            workspace_id=uuid4(),
            account_id=account.id,
            name="Чужое изменение",
            account_type=account.type,
            currency=account.currency,
            initial_balance=account.initial_balance,
            expected_updated_at=account.updated_at,
        )

    assert account.name == "Основной"


def existing_account() -> Account:
    return Account(
        id=uuid4(),
        workspace_id=uuid4(),
        name="Основной",
        type=AccountType.CARD,
        currency="RUB",
        initial_balance=Decimal("100.00"),
        is_active=True,
        updated_at=datetime(2026, 7, 30, tzinfo=UTC),
    )


def account_service(account: Account, *, has_entries: bool) -> AccountService:
    class SessionStub:
        async def commit(self) -> None:
            return None

        async def refresh(self, _: Account) -> None:
            return None

    class RepositoryStub:
        async def get_for_workspace(self, workspace_id, account_id):
            if (workspace_id, account_id) == (account.workspace_id, account.id):
                return account
            return None

        async def has_financial_history(self, workspace_id, account_id):
            return has_entries

    service = AccountService(cast(AsyncSession, SessionStub()))
    service.accounts = cast(AccountRepository, RepositoryStub())
    return service
