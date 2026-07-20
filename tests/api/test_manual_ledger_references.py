from uuid import UUID, uuid4

import pytest

from app.api.v1.manual_ledger.references import ManualLedgerReferenceReader
from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.properties.models import Property


class AccountServiceStub:
    def __init__(self) -> None:
        self.workspace_ids: list[UUID] = []

    async def list_active_accounts(self, workspace_id: UUID) -> list[Account]:
        self.workspace_ids.append(workspace_id)
        return []


class CategoryServiceStub:
    def __init__(self) -> None:
        self.workspace_ids: list[UUID] = []

    async def list_active(self, workspace_id: UUID) -> list[Category]:
        self.workspace_ids.append(workspace_id)
        return []


class PropertyServiceStub:
    def __init__(self) -> None:
        self.workspace_ids: list[UUID] = []

    async def list_active(self, workspace_id: UUID) -> list[Property]:
        self.workspace_ids.append(workspace_id)
        return []


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
