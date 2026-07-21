from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.notifications import dispatcher as notification_dispatcher
from app.features.chat_integrations.notifications.dispatcher import (
    ChatNotificationProviderRegistry,
    ChatSharedFeedNotificationService,
)
from app.features.chat_integrations.notifications.formatter import (
    ChatImportNotificationFormatter,
    ImportDocumentUploadedNotification,
)
from app.features.chat_integrations.providers.fake import FakeChatProvider
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatProviderCode,
)
from app.features.imports.models import UploadedDocumentStatus
from app.features.workspaces.service import WorkspaceContext


def test_shared_feed_import_notification_hides_financial_details() -> None:
    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="-100",
        conversation_type=ChatConversationType.GROUP,
    )

    message = ChatImportNotificationFormatter.format_document_uploaded(
        conversation,
        ImportDocumentUploadedNotification(
            workspace_name="Family",
            document_status=UploadedDocumentStatus.REQUIRES_REVIEW,
            review_url="https://booker.example/app/imports/documents/1/review",
        ),
    )

    assert "Workspace: Family" in message.text
    assert "Загружена выписка" in message.text
    assert "требует проверки" in message.text
    assert "40000" not in message.text
    assert "statement.pdf" not in message.text
    assert message.buttons[0][0].url == "https://booker.example/app/imports/documents/1/review"


@pytest.mark.asyncio
async def test_shared_feed_notification_service_sends_safe_import_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    binding_id = uuid4()
    connection_id = uuid4()
    provider = FakeChatProvider()
    session = SimpleNamespace(commit_count=0)
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4())),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    document = SimpleNamespace(
        id=uuid4(),
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        original_filename="statement.pdf",
    )
    binding = SimpleNamespace(
        id=binding_id,
        workspace_id=workspace_id,
        connection_id=connection_id,
        provider=ChatProviderCode.FAKE,
        external_chat_id="family-chat",
        conversation_type=ChatConversationType.GROUP,
    )

    async def commit() -> None:
        session.commit_count += 1

    session.commit = commit

    class FakeChatIntegrationRepository:
        def __init__(self, _session) -> None:
            self.delivery = None

        async def list_active_shared_feed_bindings(self, **_kwargs):
            return [binding]

        async def get_event_delivery(self, **_kwargs):
            return self.delivery

        async def create_event_delivery(self, **values):
            self.delivery = SimpleNamespace(id=uuid4(), status=None, **values)
            return self.delivery

        async def mark_event_delivery_sent(self, delivery, **_kwargs) -> None:
            delivery.status = "sent"

        async def mark_event_delivery_failed(self, delivery, **kwargs) -> None:
            delivery.status = "failed"
            delivery.error_message = kwargs["error_message"]

    monkeypatch.setattr(
        notification_dispatcher,
        "ChatIntegrationRepository",
        FakeChatIntegrationRepository,
    )

    summary = await ChatSharedFeedNotificationService(
        session=cast(AsyncSession, session),
        settings=Settings(public_base_url="https://booker.example"),
        provider_registry=ChatNotificationProviderRegistry({ChatProviderCode.FAKE: provider}),
    ).notify_import_document_uploaded(
        context=context,
        document=cast(Any, document),
    )

    assert summary.sent_count == 1
    assert summary.failed_count == 0
    assert session.commit_count == 1
    assert provider.sent_messages[0].conversation.external_chat_id == "family-chat"
    assert "Загружена выписка" in provider.sent_messages[0].text
    assert "statement.pdf" not in provider.sent_messages[0].text
    assert provider.sent_messages[0].buttons[0][0].url == (
        f"https://booker.example/app/imports/documents/{document.id}/review"
    )
