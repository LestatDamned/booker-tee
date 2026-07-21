from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class NamedReferenceRecord(Protocol):
    id: UUID
    name: str


class AccountReferenceRecord(NamedReferenceRecord, Protocol):
    currency: str


class AccountReferenceSource(Protocol):
    async def list_active_accounts(
        self,
        workspace_id: UUID,
    ) -> Sequence[AccountReferenceRecord]: ...


class CategoryReferenceSource(Protocol):
    async def list_active(self, workspace_id: UUID) -> Sequence[NamedReferenceRecord]: ...


class PropertyReferenceSource(Protocol):
    async def list_active(self, workspace_id: UUID) -> Sequence[NamedReferenceRecord]: ...


@dataclass(frozen=True)
class ManualLedgerAccountOptionDto:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ManualLedgerNamedOptionDto:
    id: UUID
    name: str


@dataclass(frozen=True)
class ManualLedgerReferenceOptionsDto:
    accounts: list[ManualLedgerAccountOptionDto]
    categories: list[ManualLedgerNamedOptionDto]
    properties: list[ManualLedgerNamedOptionDto]


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

    async def read(self, workspace_id: UUID) -> ManualLedgerReferenceOptionsDto:
        accounts = await self._accounts.list_active_accounts(workspace_id)
        categories = await self._categories.list_active(workspace_id)
        properties = await self._properties.list_active(workspace_id)
        return ManualLedgerReferenceOptionsDto(
            accounts=[
                ManualLedgerAccountOptionDto(
                    id=account.id,
                    name=account.name,
                    currency=account.currency,
                )
                for account in accounts
            ],
            categories=[
                ManualLedgerNamedOptionDto(id=category.id, name=category.name)
                for category in categories
            ],
            properties=[
                ManualLedgerNamedOptionDto(id=property_.id, name=property_.name)
                for property_ in properties
            ],
        )
