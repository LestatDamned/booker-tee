from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account, AccountType
from app.features.categories.models import Category, CategoryKind
from app.features.ledger.application.manual_operations import (
    ManualLedgerReferenceReader,
)
from app.features.properties.models import Property, PropertyStatus


class AccountServiceStub:
    def __init__(self, records: list[Account] | None = None) -> None:
        self.workspace_ids: list[UUID] = []
        self.records = records or []

    async def list_active_accounts(self, workspace_id: UUID) -> list[Account]:
        self.workspace_ids.append(workspace_id)
        return self.records


class CategoryServiceStub:
    def __init__(self, records: list[Category] | None = None) -> None:
        self.workspace_ids: list[UUID] = []
        self.records = records or []

    async def list_active(self, workspace_id: UUID) -> list[Category]:
        self.workspace_ids.append(workspace_id)
        return self.records


class PropertyServiceStub:
    def __init__(self, records: list[Property] | None = None) -> None:
        self.workspace_ids: list[UUID] = []
        self.records = records or []

    async def list_active(self, workspace_id: UUID) -> list[Property]:
        self.workspace_ids.append(workspace_id)
        return self.records


@pytest.mark.asyncio
async def test_reference_reader_uses_read_only_workspace_scoped_services() -> None:
    workspace_id = uuid4()
    accounts = AccountServiceStub()
    categories = CategoryServiceStub()
    properties = PropertyServiceStub()
    reader = ManualLedgerReferenceReader(
        accounts=accounts,
        categories=categories,
        properties=properties,
    )

    references = await reader.read(workspace_id)

    assert references.accounts == []
    assert references.categories == []
    assert references.properties == []
    assert accounts.workspace_ids == [workspace_id]
    assert categories.workspace_ids == [workspace_id]
    assert properties.workspace_ids == [workspace_id]


@pytest.mark.asyncio
async def test_reference_reader_returns_narrow_immutable_options() -> None:
    workspace_id = uuid4()
    account_id = uuid4()
    category_id = uuid4()
    property_id = uuid4()
    reader = ManualLedgerReferenceReader(
        accounts=AccountServiceStub(
            [
                Account(
                    id=account_id,
                    workspace_id=workspace_id,
                    name="Основной счёт",
                    type=AccountType.CHECKING,
                    currency="RUB",
                    initial_balance=Decimal("0.00"),
                )
            ]
        ),
        categories=CategoryServiceStub(
            [
                Category(
                    id=category_id,
                    workspace_id=workspace_id,
                    name="Аренда",
                    kind=CategoryKind.INCOME,
                    sort_order=100,
                )
            ]
        ),
        properties=PropertyServiceStub(
            [
                Property(
                    id=property_id,
                    workspace_id=workspace_id,
                    name="Квартира",
                    status=PropertyStatus.ACTIVE,
                )
            ]
        ),
    )

    references = await reader.read(workspace_id)

    assert references.accounts[0].id == account_id
    assert references.accounts[0].currency == "RUB"
    assert references.categories[0].id == category_id
    assert references.properties[0].id == property_id
