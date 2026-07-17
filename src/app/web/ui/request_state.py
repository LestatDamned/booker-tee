from dataclasses import dataclass
from typing import Literal

from app.web.ui.actions import ActionVM

RequestPhase = Literal["idle", "loading", "error"]


@dataclass(frozen=True)
class FieldErrorVM:
    field_id: str
    error_id: str
    message: str


@dataclass(frozen=True)
class RequestStateVM:
    phase: RequestPhase = "idle"
    message: str | None = None
    retry_action: ActionVM | None = None

    @property
    def is_busy(self) -> bool:
        return self.phase == "loading"

    @property
    def has_error(self) -> bool:
        return self.phase == "error" and self.message is not None
