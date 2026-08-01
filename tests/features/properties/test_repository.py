from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.properties.models import Property, PropertyStatus
from app.features.properties.repository import PropertyRepository


class ScalarRows:
    def __init__(self, rows: list[Property]) -> None:
        self.rows = rows

    def all(self) -> list[Property]:
        return self.rows


class QueryResult:
    def __init__(self, rows: list[Property]) -> None:
        self.rows = rows

    def scalars(self) -> ScalarRows:
        return ScalarRows(self.rows)


class SessionCapture:
    def __init__(self, rows: list[Property]) -> None:
        self.rows = rows
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> QueryResult:
        self.queries.append(query)
        return QueryResult(self.rows)


@pytest.mark.asyncio
async def test_active_property_options_are_workspace_and_status_scoped() -> None:
    workspace_id = uuid4()
    active = Property(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Квартира",
        status=PropertyStatus.ACTIVE,
    )
    session = SessionCapture([active])

    rows = await PropertyRepository(cast(AsyncSession, session)).list_active_for_workspace(
        workspace_id
    )

    assert rows == [active]
    compiled = session.queries[0].compile()
    sql = str(compiled)
    assert "properties.workspace_id" in sql
    assert "properties.status" in sql
    assert workspace_id in compiled.params.values()
    assert PropertyStatus.ACTIVE in compiled.params.values()
