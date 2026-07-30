from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.accounts.service import (
    AccountCurrencyConflictError,
    AccountError,
    AccountService,
    AccountUpdateConflictError,
    normalize_currency,
)


def test_normalize_currency_uppercases_three_letter_code() -> None:
    assert normalize_currency("rub") == "RUB"


def test_normalize_currency_rejects_invalid_code() -> None:
    with pytest.raises(AccountError):
        normalize_currency("rouble")


def test_decimal_initial_balance_can_be_quantized_without_float() -> None:
    assert Decimal("10").quantize(Decimal("0.01")) == Decimal("10.00")


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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
