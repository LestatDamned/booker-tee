from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountDirectoryRow
from app.features.accounts.schemas import (
    AccountBalanceDirection,
    AccountDirectoryCapabilitiesDto,
    AccountDirectoryDto,
    AccountDirectoryReadonlyReason,
    AccountSummaryDto,
    CreateAccountCommand,
    UpdateAccountCommand,
)


class AccountDirectorySource(Protocol):
    async def list_directory_rows(
        self,
        workspace_id: UUID,
    ) -> Sequence[AccountDirectoryRow]: ...


class AccountMutationSource(Protocol):
    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        account_type: AccountType,
        currency: str,
        initial_balance: Decimal,
    ) -> Account: ...

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        is_active: bool,
        expected_active: bool | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Account: ...

    async def update(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        name: str,
        account_type: AccountType,
        currency: str,
        initial_balance: Decimal,
        expected_updated_at: datetime | None = None,
    ) -> Account: ...


class AccountDirectoryService:
    def __init__(
        self,
        *,
        accounts: AccountDirectorySource,
        creator: AccountMutationSource,
    ) -> None:
        self._accounts = accounts
        self._creator = creator

    async def read(
        self,
        *,
        workspace_id: UUID,
        can_create: bool,
    ) -> AccountDirectoryDto:
        rows = await self._accounts.list_directory_rows(workspace_id)
        return AccountDirectoryDto(
            items=[account_summary_from_row(row) for row in rows],
            account_types=AccountType.user_managed(),
            capabilities=AccountDirectoryCapabilitiesDto(
                can_create=can_create,
                readonly_reason_code=(
                    None if can_create else AccountDirectoryReadonlyReason.FINANCIAL_WRITE_FORBIDDEN
                ),
            ),
        )

    async def create(
        self,
        *,
        workspace_id: UUID,
        command: CreateAccountCommand,
    ) -> AccountSummaryDto:
        account = await self._creator.create(
            workspace_id=workspace_id,
            name=command.name,
            account_type=command.account_type,
            currency=command.currency,
            initial_balance=command.initial_balance,
        )
        return AccountSummaryDto(
            id=account.id,
            name=account.name,
            account_type=account.type,
            currency=account.currency,
            initial_balance=account.initial_balance,
            balance=account.initial_balance,
            balance_direction=balance_direction(account.initial_balance),
            movement_count=0,
            is_active=account.is_active,
            updated_at=account.updated_at,
        )

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        is_active: bool,
        expected_active: bool,
        expected_updated_at: datetime,
    ) -> AccountSummaryDto:
        await self._creator.set_active(
            workspace_id=workspace_id,
            account_id=account_id,
            is_active=is_active,
            expected_active=expected_active,
            expected_updated_at=expected_updated_at,
        )
        rows = await self._accounts.list_directory_rows(workspace_id)
        row = next((item for item in rows if item.id == account_id), None)
        if row is None:
            raise RuntimeError("Committed account is missing from its workspace directory.")
        return account_summary_from_row(row)

    async def update(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        command: UpdateAccountCommand,
    ) -> AccountSummaryDto:
        await self._creator.update(
            workspace_id=workspace_id,
            account_id=account_id,
            name=command.name,
            account_type=command.account_type,
            currency=command.currency,
            initial_balance=command.initial_balance,
            expected_updated_at=command.expected_updated_at,
        )
        rows = await self._accounts.list_directory_rows(workspace_id)
        row = next((item for item in rows if item.id == account_id), None)
        if row is None:
            raise RuntimeError("Committed account is missing from its workspace directory.")
        return account_summary_from_row(row)


def account_summary_from_row(row: AccountDirectoryRow) -> AccountSummaryDto:
    balance = (row.initial_balance + row.confirmed_entry_total).quantize(Decimal("0.01"))
    return AccountSummaryDto(
        id=row.id,
        name=row.name,
        account_type=row.account_type,
        currency=row.currency,
        initial_balance=row.initial_balance,
        balance=balance,
        balance_direction=balance_direction(balance),
        movement_count=row.confirmed_movement_count,
        is_active=row.is_active,
        updated_at=row.updated_at,
    )


def balance_direction(balance: Decimal) -> AccountBalanceDirection:
    if balance > 0:
        return AccountBalanceDirection.POSITIVE
    if balance < 0:
        return AccountBalanceDirection.NEGATIVE
    return AccountBalanceDirection.ZERO
