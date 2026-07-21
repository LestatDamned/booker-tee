from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations import application as chat_application
from app.features.chat_integrations import service as chat_service
from app.features.chat_integrations.handlers import upload as chat_upload_handler
from app.features.chat_integrations.providers.fake import FakeChatProvider
from app.features.chat_integrations.schemas import (
    ChatConversation,
    ChatConversationType,
    ChatDocument,
    ChatProviderCode,
    ChatUser,
    InboundChatEvent,
    InboundChatEventType,
)
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.use_cases import dashboard as chat_dashboard
from app.features.chat_integrations.use_cases import workspace as chat_workspace
from app.features.imports.models import UploadedDocumentStatus
from app.features.workspaces.service import WorkspaceContext


@pytest.mark.asyncio
async def test_chat_event_service_shows_upload_instructions_for_bound_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatPrivateStatusReader:
        def __init__(self, _session: object) -> None:
            pass

        async def read_status(self, _context: WorkspaceContext) -> chat_dashboard.ChatPrivateStatus:
            return chat_dashboard.ChatPrivateStatus(
                documents_needing_attention=0,
                raw_transactions_needing_attention=0,
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(chat_service, "ChatPrivateStatusReader", FakeChatPrivateStatusReader)

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="upload:start",
    )

    response = await ChatEventService(cast(AsyncSession, object())).receive_inbound_event(event)

    assert response is not None
    assert "📎 Загрузка выписки" in response.text
    assert "Отправь PDF или XLSX файлом" in response.text
    assert response.buttons[0][0].callback_data == "main:menu"


@pytest.mark.asyncio
async def test_chat_event_service_starts_document_upload_for_bound_private_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatDocumentUploadService:
        def __init__(self, _session: object, _settings: Settings, _downloader: object) -> None:
            pass

        async def start_document_upload(self, **kwargs):
            assert kwargs["context"] is context
            assert kwargs["document"].file_id == "file-id"
            return chat_application.StartedChatDocumentUpload(
                action_token="uploadtoken",
                account_choices=(
                    chat_application.ChatAccountChoice(name="T-Bank Card", currency="RUB"),
                ),
            )

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_upload_handler, "ChatDocumentUploadService", FakeChatDocumentUploadService
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.DOCUMENT,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        document=ChatDocument(
            file_id="file-id",
            file_name="statement.pdf",
            mime_type="application/pdf",
        ),
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(),
        cast(Any, object()),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выбери счет" in response.text
    assert response.buttons[0][0].text == "T-Bank Card / RUB"
    assert response.buttons[0][0].callback_data == "upl:uploadtoken:0"


@pytest.mark.asyncio
async def test_chat_event_service_completes_document_upload_after_account_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    uploaded_document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
    )

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatDocumentUploadService:
        def __init__(self, _session: object, _settings: Settings, _downloader: object) -> None:
            pass

        async def complete_document_upload(self, **kwargs):
            assert kwargs == {
                "context": context,
                "action_token": "uploadtoken",
                "account_index": 0,
            }
            return uploaded_document

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_upload_handler, "ChatDocumentUploadService", FakeChatDocumentUploadService
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="upl:uploadtoken:0",
    )

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
        cast(Any, object()),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выписка загружена" in response.text
    assert "требует проверки" in response.text
    assert response.buttons[0][0].text == "🔎 Проверка"
    assert response.buttons[0][0].callback_data == "review:choose"
    assert response.buttons[0][1].callback_data == "status:show"
    assert response.buttons[0][2].text == "🌐 Web"
    assert response.buttons[0][2].url == (
        f"https://booker.example/app/imports/documents/{uploaded_document.id}/review"
    )


@pytest.mark.asyncio
async def test_chat_event_service_notifies_shared_feed_after_document_upload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4(), name="Anna", email="anna@example.test")),
        workspace=cast(Any, SimpleNamespace(id=workspace_id, name="Family")),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )
    bound_workspace = chat_workspace.BoundChatWorkspace(
        identity_binding=cast(Any, SimpleNamespace(id=uuid4())),
        context=context,
    )
    uploaded_document = SimpleNamespace(
        id=uuid4(),
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
    )
    notified_documents: list[object] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatDocumentUploadService:
        def __init__(self, _session: object, _settings: Settings, _downloader: object) -> None:
            pass

        async def complete_document_upload(self, **_kwargs):
            return uploaded_document

    class FakeChatSharedFeedNotificationService:
        def __init__(self, **_kwargs) -> None:
            pass

        async def notify_import_document_uploaded(self, **kwargs) -> None:
            assert kwargs["context"] is context
            notified_documents.append(kwargs["document"])

    monkeypatch.setattr(chat_service, "WorkspaceChatResolver", FakeWorkspaceChatResolver)
    monkeypatch.setattr(
        chat_upload_handler, "ChatDocumentUploadService", FakeChatDocumentUploadService
    )
    monkeypatch.setattr(
        chat_upload_handler,
        "ChatSharedFeedNotificationService",
        FakeChatSharedFeedNotificationService,
    )

    conversation = ChatConversation(
        provider=ChatProviderCode.TELEGRAM,
        external_chat_id="42",
        conversation_type=ChatConversationType.PRIVATE,
    )
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=conversation,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="upl:uploadtoken:0",
    )
    provider = FakeChatProvider()

    await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
        cast(Any, object()),
        provider,
    ).receive_inbound_event(event)

    assert notified_documents == [uploaded_document]
