from dataclasses import dataclass
from uuid import UUID

from app.features.chat_integrations.schemas import ChatProviderCode


@dataclass(frozen=True)
class BindChatIdentityCommand:
    workspace_id: UUID
    user_id: UUID
    provider: ChatProviderCode
    external_user_id: str
    display_name: str | None = None
