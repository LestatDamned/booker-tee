from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.properties.models import Property


class AccountReferenceSource(Protocol):
    async def list_active_accounts(self, workspace_id: UUID) -> Sequence[Account]: ...


class CategoryReferenceSource(Protocol):
    async def list_active(self, workspace_id: UUID) -> Sequence[Category]: ...


class PropertyReferenceSource(Protocol):
    async def list_active(self, workspace_id: UUID) -> Sequence[Property]: ...


@dataclass(frozen=True)
class ManualLedgerReferences:
    accounts: list[Account]
    categories: list[Category]
    properties: list[Property]


class ManualLedgerReferenceReader:
    def __init__(
        self,
        *,
        accounts: AccountReferenceSource,
        categories: CategoryReferenceSource,
        properties: PropertyReferenceSource,
    ) -> None:
        self._accounts = accounts
        self._categories = categories
        self._properties = properties

    async def read(self, workspace_id: UUID) -> ManualLedgerReferences:
        return ManualLedgerReferences(
            accounts=list(await self._accounts.list_active_accounts(workspace_id)),
            categories=list(await self._categories.list_active(workspace_id)),
            properties=list(await self._properties.list_active(workspace_id)),
        )
