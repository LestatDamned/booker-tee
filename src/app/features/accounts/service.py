from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository


class AccountError(ValueError):
    pass


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)

    async def list_or_create_default(self, workspace_id: UUID, currency: str) -> list[Account]:
        accounts = await self.accounts.list_active_for_workspace(workspace_id)
        if accounts:
            return accounts

        account = await self.accounts.create_parser_lab_account(workspace_id, currency)
        await self.session.commit()
        return [account]

    async def list_accounts(self, workspace_id: UUID) -> list[Account]:
        return await self.accounts.list_for_workspace(workspace_id)

    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        account_type: AccountType,
        currency: str,
        initial_balance: Decimal,
    ) -> Account:
        cleaned_name = clean_required_text(name, "Название счета обязательно.")
        account = await self.accounts.create(
            Account(
                workspace_id=workspace_id,
                name=cleaned_name,
                type=account_type,
                currency=normalize_currency(currency),
                initial_balance=initial_balance.quantize(Decimal("0.01")),
            )
        )
        await self.session.commit()
        return account

    async def update(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        name: str,
        account_type: AccountType,
        currency: str,
        initial_balance: Decimal,
    ) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            raise AccountError("Счет не найден в этом workspace.")
        account.name = clean_required_text(name, "Название счета обязательно.")
        account.type = account_type
        account.currency = normalize_currency(currency)
        account.initial_balance = initial_balance.quantize(Decimal("0.01"))
        await self.session.commit()
        return account

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        is_active: bool,
    ) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            raise AccountError("Счет не найден в этом workspace.")
        account.is_active = is_active
        account.archived_at = None if is_active else utc_now()
        await self.session.commit()
        return account


def clean_required_text(value: str, message: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise AccountError(message)
    return cleaned


def normalize_currency(value: str) -> str:
    currency = clean_required_text(value, "Валюта обязательна.").upper()
    if len(currency) != 3:
        raise AccountError("Валюта должна быть трехбуквенным кодом.")
    return currency
