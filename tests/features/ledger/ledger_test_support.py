from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4


def workspace_context(workspace_id: UUID) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=uuid4()),
        ),
    )
