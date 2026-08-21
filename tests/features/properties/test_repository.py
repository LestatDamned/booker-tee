from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.properties.models import Property, PropertyStatus
from app.features.properties.repository import PropertyRepository


async def test_property_lookup_is_workspace_scoped() -> None:
    workspace_id = uuid4()
    property_id = uuid4()
    execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: None),
    )

    result = await PropertyRepository(
        cast(AsyncSession, SimpleNamespace(execute=execute))
    ).get_for_workspace(workspace_id, property_id)

    assert result is None
    assert execute.await_args is not None
    compiled = execute.await_args.args[0].compile()
    sql = str(compiled)
    assert "properties.id" in sql
    assert "properties.workspace_id" in sql
    assert {workspace_id, property_id} <= set(compiled.params.values())


async def test_active_property_options_are_workspace_and_status_scoped() -> None:
    workspace_id = uuid4()
    active = Property(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Квартира",
        status=PropertyStatus.ACTIVE,
    )
    execute = AsyncMock(
        return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [active]),
        )
    )
    session = SimpleNamespace(execute=execute)

    rows = await PropertyRepository(cast(AsyncSession, session)).list_active_for_workspace(
        workspace_id
    )

    assert rows == [active]
    assert execute.await_args is not None
    compiled = execute.await_args.args[0].compile()
    sql = str(compiled)
    assert "properties.workspace_id" in sql
    assert "properties.status" in sql
    assert workspace_id in compiled.params.values()
    assert PropertyStatus.ACTIVE in compiled.params.values()
