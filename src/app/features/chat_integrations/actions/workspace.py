from dataclasses import dataclass


@dataclass(frozen=True)
class ChatWorkspaceSelection:
    action_token: str
    workspace_index: int


class ChatWorkspaceCallbackData:
    PREFIX = "wsp"

    @classmethod
    def build_workspace_selection(cls, *, action_token: str, workspace_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{workspace_index}"

    @classmethod
    def parse_workspace_selection(
        cls,
        callback_data: str | None,
    ) -> ChatWorkspaceSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            workspace_index = int(parts[2])
        except ValueError:
            return None
        return ChatWorkspaceSelection(
            action_token=parts[1],
            workspace_index=workspace_index,
        )
