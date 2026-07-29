from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.chat_integrations.application import ChatReviewUrlBuilder
from app.features.chat_integrations.models import ChatConversationBinding
from app.features.chat_integrations.notifications.formatter import (
    ChatImportNotificationFormatter,
    ImportDocumentUploadedNotification,
)
from app.features.chat_integrations.providers.base import ChatProvider
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.schemas import ChatConversation, ChatProviderCode
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.workspaces.service import WorkspaceContext

IMPORT_DOCUMENT_UPLOADED_EVENT = "import.document_uploaded"


@dataclass(frozen=True)
class ChatNotificationDeliverySummary:
    attempted_count: int
    sent_count: int
    failed_count: int
    skipped_count: int


class ChatNotificationProviderRegistry:
    def __init__(self, providers: dict[ChatProviderCode, ChatProvider]) -> None:
        self.providers = providers

    def get_provider(self, provider_code: ChatProviderCode) -> ChatProvider | None:
        return self.providers.get(provider_code)


class ChatSharedFeedNotificationService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings | None,
        provider_registry: ChatNotificationProviderRegistry,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider_registry = provider_registry
        self.chat_integrations = ChatIntegrationRepository(session)

    async def notify_import_document_uploaded(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        document_status: UploadedDocumentStatus,
    ) -> ChatNotificationDeliverySummary:
        bindings = await self.chat_integrations.list_active_shared_feed_bindings(
            workspace_id=context.workspace.id
        )
        attempted_count = 0
        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for binding in bindings:
            result = await self._notify_binding(
                binding=binding,
                context=context,
                document_id=document_id,
                document_status=document_status,
            )
            attempted_count += result.attempted_count
            sent_count += result.sent_count
            failed_count += result.failed_count
            skipped_count += result.skipped_count

        await self.session.commit()
        return ChatNotificationDeliverySummary(
            attempted_count=attempted_count,
            sent_count=sent_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )

    async def _notify_binding(
        self,
        *,
        binding: ChatConversationBinding,
        context: WorkspaceContext,
        document_id: UUID,
        document_status: UploadedDocumentStatus,
    ) -> ChatNotificationDeliverySummary:
        idempotency_key = ChatNotificationIdempotencyKeyBuilder.import_document_uploaded(
            document_id=document_id,
            binding_id=binding.id,
        )
        existing_delivery = await self.chat_integrations.get_event_delivery(
            workspace_id=context.workspace.id,
            connection_id=binding.connection_id,
            idempotency_key=idempotency_key,
        )
        if existing_delivery is not None:
            return ChatNotificationDeliverySummary(
                attempted_count=0,
                sent_count=0,
                failed_count=0,
                skipped_count=1,
            )

        delivery = await self.chat_integrations.create_event_delivery(
            workspace_id=context.workspace.id,
            connection_id=binding.connection_id,
            binding_id=binding.id,
            event_type=IMPORT_DOCUMENT_UPLOADED_EVENT,
            idempotency_key=idempotency_key,
        )
        provider = self.provider_registry.get_provider(binding.provider)
        if provider is None:
            await self.chat_integrations.mark_event_delivery_failed(
                delivery,
                error_message="Provider is not available.",
            )
            return ChatNotificationDeliverySummary(1, 0, 1, 0)

        message = ChatImportNotificationFormatter.format_document_uploaded(
            ChatConversationBindingMapper.to_conversation(binding),
            ImportDocumentUploadedNotification(
                workspace_name=context.workspace.name,
                document_status=document_status,
                review_url=ChatReviewUrlBuilder.build_document_review_url(
                    self.settings,
                    document_id,
                ),
            ),
        )
        try:
            await provider.send_message(message)
        except Exception as exc:
            await self.chat_integrations.mark_event_delivery_failed(
                delivery,
                error_message=ChatDeliveryErrorFormatter.safe_message(exc),
            )
            return ChatNotificationDeliverySummary(1, 0, 1, 0)

        await self.chat_integrations.mark_event_delivery_sent(delivery, sent_at=utc_now())
        return ChatNotificationDeliverySummary(1, 1, 0, 0)


class ChatConversationBindingMapper:
    @staticmethod
    def to_conversation(binding: ChatConversationBinding) -> ChatConversation:
        return ChatConversation(
            provider=binding.provider,
            external_chat_id=binding.external_chat_id,
            conversation_type=binding.conversation_type,
        )


class ChatNotificationIdempotencyKeyBuilder:
    @staticmethod
    def import_document_uploaded(*, document_id: UUID, binding_id: UUID) -> str:
        return f"{IMPORT_DOCUMENT_UPLOADED_EVENT}:{document_id}:{binding_id}"


class ChatDeliveryErrorFormatter:
    @staticmethod
    def safe_message(exc: Exception) -> str:
        message = str(exc) or exc.__class__.__name__
        return message[:512]
