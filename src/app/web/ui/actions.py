from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ActionKind = Literal["link", "submit", "disclosure"]
SubmitMethod = Literal["post"]
SubmitSwap = Literal["outerHTML", "innerHTML"]


@dataclass(frozen=True, kw_only=True)
class LinkActionVM:
    label: str
    url: str
    icon: str
    disabled: bool = False
    disabled_reason: str | None = None
    kind: Literal["link"] = "link"


@dataclass(frozen=True, kw_only=True)
class SubmitActionVM:
    label: str
    url: str
    icon: str
    method: SubmitMethod = "post"
    confirmation: str | None = None
    hidden_fields: Mapping[str, str] | None = None
    target_id: str | None = None
    swap: SubmitSwap = "outerHTML"
    disabled: bool = False
    disabled_reason: str | None = None
    kind: Literal["submit"] = "submit"


@dataclass(frozen=True, kw_only=True)
class DisclosureActionVM:
    label: str
    fallback_url: str
    load_url: str
    panel_id: str
    load_target_id: str
    icon: str
    disabled: bool = False
    disabled_reason: str | None = None
    kind: Literal["disclosure"] = "disclosure"


type ActionVM = LinkActionVM | SubmitActionVM | DisclosureActionVM


@dataclass(frozen=True)
class ActionSetVM:
    primary: ActionVM | None = None
    secondary: tuple[ActionVM, ...] = ()
    menu: tuple[ActionVM, ...] = ()
    danger: tuple[ActionVM, ...] = ()
