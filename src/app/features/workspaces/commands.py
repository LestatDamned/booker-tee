from dataclasses import dataclass

from app.features.workspaces.models import WorkspaceType


@dataclass(frozen=True)
class CreateWorkspaceCommand:
    name: str
    workspace_type: WorkspaceType
    default_currency: str = "RUB"


@dataclass(frozen=True)
class UpdateWorkspaceCommand:
    name: str
    workspace_type: WorkspaceType
    default_currency: str
