from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
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
from app.features.imports.documents.commands.upload import StatementUploadResult
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.workspaces.service import WorkspaceContext


def test_telegram_document_uses_configured_upload_limit() -> None:
    document = ChatDocument(
        file_id="file-id",
        file_name="statement.pdf",
        file_size=1025,
    )

    with pytest.raises(chat_application.ChatDocumentUploadError, match="size limit"):
        chat_application.ChatDocumentUploadPolicy.ensure_supported_statement(
            document,
            max_bytes=1024,
        )


@pytest.mark.asyncio
async def test_telegram_upload_uses_conversation_state_as_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    user_id = uuid4()
    account_id = uuid4()
    state_id = uuid4()
    state = SimpleNamespace(
        id=state_id,
        state_payload={
            "file_id": "file-id",
            "file_name": "statement.pdf",
            "account_ids": [str(account_id)],
        },
    )
    upload_result = StatementUploadResult(
        document_id=uuid4(),
        document_status=UploadedDocumentStatus.REQUIRES_REVIEW,
        filename="statement.pdf",
        replayed=False,
    )
    seen_idempotency_keys: list[object] = []

    class FakeUploads:
        def __init__(self, *_args: object) -> None:
            pass

        async def upload_statement(self, **kwargs: object) -> StatementUploadResult:
            seen_idempotency_keys.append(kwargs["idempotency_key"])
            return upload_result

    chat_repository = SimpleNamespace(
        get_active_conversation_state=AsyncMock(return_value=state),
        consume_conversation_state=AsyncMock(),
    )
    session = SimpleNamespace(commit=AsyncMock())
    downloader = SimpleNamespace(
        download_document=AsyncMock(
            return_value=SimpleNamespace(
                filename="statement.pdf",
                content_type="application/pdf",
                file_bytes=b"pdf",
            )
        )
    )
    monkeypatch.setattr(chat_application, "StatementUploadUseCase", FakeUploads)
    service = chat_application.ChatDocumentUploadService(
        cast(AsyncSession, session),
        Settings(),
        cast(Any, downloader),
    )
    service.chat_integrations = cast(Any, chat_repository)

    result = await service.complete_document_upload(
        context=WorkspaceContext(
            user=cast(Any, SimpleNamespace(id=user_id)),
            workspace=cast(Any, SimpleNamespace(id=workspace_id)),
            membership=cast(Any, SimpleNamespace()),
        ),
        action_token="upload-token",
        account_index=0,
    )

    assert result == upload_result
    assert seen_idempotency_keys == [state_id]
    assert state.state_payload == {}
    chat_repository.consume_conversation_state.assert_awaited_once()


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
    upload_result = StatementUploadResult(
        document_id=uuid4(),
        document_status=UploadedDocumentStatus.REQUIRES_REVIEW,
        filename="statement.pdf",
        replayed=False,
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
            return upload_result

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
    assert "удалится через 48 часов" in response.text
    assert "удали сообщение с файлом" in response.text
    assert "Telegram хранит свою копию отдельно" in response.text
    assert response.buttons[0][0].text == "🔎 Проверка"
    assert response.buttons[0][0].callback_data == "review:choose"
    assert response.buttons[0][1].callback_data == "status:show"
    assert response.buttons[0][2].text == "🌐 Web"
    assert response.buttons[0][2].url == (
        f"https://booker.example/app/imports/documents/{upload_result.document_id}/review"
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
    upload_result = StatementUploadResult(
        document_id=uuid4(),
        document_status=UploadedDocumentStatus.REQUIRES_REVIEW,
        filename="statement.pdf",
        replayed=False,
    )
    notified_documents: list[tuple[object, object]] = []

    class FakeWorkspaceChatResolver:
        def __init__(self, _session: object) -> None:
            pass

        async def require_bound_workspace(self, _event: InboundChatEvent):
            return bound_workspace

    class FakeChatDocumentUploadService:
        def __init__(self, _session: object, _settings: Settings, _downloader: object) -> None:
            pass

        async def complete_document_upload(self, **_kwargs):
            return upload_result

    class FakeChatSharedFeedNotificationService:
        def __init__(self, **_kwargs) -> None:
            pass

        async def notify_import_document_uploaded(self, **kwargs) -> None:
            assert kwargs["context"] is context
            notified_documents.append((kwargs["document_id"], kwargs["document_status"]))

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

    assert notified_documents == [(upload_result.document_id, upload_result.document_status)]
