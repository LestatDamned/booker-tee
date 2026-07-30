from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository


class AccountError(ValueError):
    pass


class AccountNotFoundError(AccountError):
    pass


class AccountLifecycleConflictError(AccountError):
    pass


class AccountUpdateConflictError(AccountError):
    pass


class AccountCurrencyConflictError(AccountError):
    pass


class AccountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)

    async def list_active_accounts(self, workspace_id: UUID) -> list[Account]:
        return await self.accounts.list_active_for_workspace(workspace_id)

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
        expected_updated_at: datetime | None = None,
    ) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            raise AccountNotFoundError("Счет не найден в этом workspace.")
        if expected_updated_at is not None and account.updated_at != expected_updated_at:
            raise AccountUpdateConflictError("Счёт уже изменился в другом окне.")
        normalized_currency = normalize_currency(currency)
        if normalized_currency != account.currency and await self.accounts.has_financial_history(
            workspace_id, account_id
        ):
            raise AccountCurrencyConflictError(
                "Нельзя изменить валюту счёта с финансовой историей."
            )
        account.name = clean_required_text(name, "Название счета обязательно.")
        account.type = account_type
        account.currency = normalized_currency
        account.initial_balance = initial_balance.quantize(Decimal("0.01"))
        await self.session.commit()
        await self.session.refresh(account)
        return account

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        is_active: bool,
        expected_active: bool | None = None,
        expected_updated_at: datetime | None = None,
    ) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            raise AccountNotFoundError("Счет не найден в этом workspace.")
        if expected_active is not None and account.is_active is not expected_active:
            raise AccountLifecycleConflictError("Состояние счета уже изменилось.")
        if expected_updated_at is not None and account.updated_at != expected_updated_at:
            raise AccountLifecycleConflictError("Счет уже изменился в другом окне.")
        account.is_active = is_active
        account.archived_at = None if is_active else utc_now()
        await self.session.commit()
        await self.session.refresh(account)
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
