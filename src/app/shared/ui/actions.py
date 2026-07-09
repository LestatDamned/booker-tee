from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ActionPlacement = Literal["primary", "secondary", "danger", "technical", "menu"]
ActionStyle = Literal["default", "danger", "muted", "success"]
ActionType = Literal["post", "link", "panel_toggle", "submit", "drawer_toggle", "readonly"]


@dataclass(frozen=True)
class ActionVM:
    id: str
    label: str
    icon: str
    placement: ActionPlacement | str
    action_type: ActionType | str
    url: str | None = None
    style: ActionStyle | str = "default"
    form_id: str | None = None
    hidden_fields: Mapping[str, str] | None = None
    panel_id: str | None = None
    confirm_message: str | None = None

    @property
    def form_action(self) -> str:
        return self.url or ""

    @property
    def href(self) -> str | None:
        return self.url
