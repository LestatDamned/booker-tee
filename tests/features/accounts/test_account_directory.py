from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.features.accounts.application.directory import AccountDirectoryService
from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountDirectoryRow
from app.features.accounts.schemas import (
    AccountBalanceDirection,
    AccountDirectoryReadonlyReason,
    CreateAccountCommand,
)


class AccountDirectorySourceStub:
    def __init__(self, rows: list[AccountDirectoryRow]) -> None:
        self.rows = rows
        self.workspace_ids: list[UUID] = []

    async def list_directory_rows(
        self,
        workspace_id: UUID,
    ) -> list[AccountDirectoryRow]:
        self.workspace_ids.append(workspace_id)
        return self.rows


class AccountCreationSourceStub:
    def __init__(self, account: Account) -> None:
        self.account = account
        self.calls: list[dict[str, object]] = []

    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        account_type: AccountType,
        currency: str,
        initial_balance: Decimal,
    ) -> Account:
        self.calls.append(
            {
                "workspace_id": workspace_id,
                "name": name,
                "account_type": account_type,
                "currency": currency,
                "initial_balance": initial_balance,
            }
        )
        return self.account

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        is_active: bool,
        expected_active: bool | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Account:
        self.account.is_active = is_active
        return self.account


@pytest.mark.asyncio
async def test_account_directory_builds_authoritative_summaries_from_one_read() -> None:
    workspace_id = uuid4()
    account_id = uuid4()
    updated_at = datetime(2026, 7, 30, tzinfo=UTC)
    source = AccountDirectorySourceStub(
        [
            AccountDirectoryRow(
                id=account_id,
                name="Основной",
                account_type=AccountType.CARD,
                currency="RUB",
                initial_balance=Decimal("100.00"),
                is_active=True,
                updated_at=updated_at,
                confirmed_entry_total=Decimal("-25.50"),
                confirmed_movement_count=3,
            )
        ]
    )
    service = AccountDirectoryService(
        accounts=source,
        creator=AccountCreationSourceStub(account()),
    )

    result = await service.read(workspace_id=workspace_id, can_create=False)

    assert source.workspace_ids == [workspace_id]
    assert result.items[0].model_dump() == {
        "id": account_id,
        "name": "Основной",
        "account_type": AccountType.CARD,
        "currency": "RUB",
        "initial_balance": Decimal("100.00"),
        "balance": Decimal("74.50"),
        "balance_direction": AccountBalanceDirection.POSITIVE,
        "movement_count": 3,
        "is_active": True,
        "updated_at": updated_at,
    }
    assert result.capabilities.can_create is False
    assert (
        result.capabilities.readonly_reason_code
        is AccountDirectoryReadonlyReason.FINANCIAL_WRITE_FORBIDDEN
    )


@pytest.mark.asyncio
async def test_account_directory_create_returns_committed_account_summary() -> None:
    workspace_id = uuid4()
    created = account(
        workspace_id=workspace_id,
        initial_balance=Decimal("-1500.00"),
    )
    creator = AccountCreationSourceStub(created)
    service = AccountDirectoryService(
        accounts=AccountDirectorySourceStub([]),
        creator=creator,
    )
    command = CreateAccountCommand(
        name="Резерв",
        account_type=AccountType.DEPOSIT,
        currency="RUB",
        initial_balance=Decimal("-1500.00"),
    )

    result = await service.create(workspace_id=workspace_id, command=command)

    assert creator.calls == [
        {
            "workspace_id": workspace_id,
            "name": "Резерв",
            "account_type": AccountType.DEPOSIT,
            "currency": "RUB",
            "initial_balance": Decimal("-1500.00"),
        }
    ]
    assert result.id == created.id
    assert result.balance == Decimal("-1500.00")
    assert result.balance_direction is AccountBalanceDirection.NEGATIVE
    assert result.movement_count == 0


def account(
    *,
    workspace_id: UUID | None = None,
    initial_balance: Decimal = Decimal("0.00"),
) -> Account:
    return Account(
        id=uuid4(),
        workspace_id=workspace_id or uuid4(),
        name="Резерв",
        type=AccountType.DEPOSIT,
        currency="RUB",
        initial_balance=initial_balance,
        is_active=True,
        updated_at=datetime(2026, 7, 30, tzinfo=UTC),
    )
