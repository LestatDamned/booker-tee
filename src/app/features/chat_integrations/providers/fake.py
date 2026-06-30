from dataclasses import dataclass, field

from app.features.chat_integrations.schemas import InboundChatEvent, OutboundChatMessage


@dataclass
class FakeChatProvider:
    sent_messages: list[OutboundChatMessage] = field(default_factory=list)
    inbound_events: list[InboundChatEvent] = field(default_factory=list)

    async def send_message(self, message: OutboundChatMessage) -> None:
        self.sent_messages.append(message)

    def push_event(self, event: InboundChatEvent) -> None:
        self.inbound_events.append(event)
