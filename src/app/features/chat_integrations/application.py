from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.accounts.service import AccountService
from app.features.chat_integrations.errors import (
    ChatDocumentUploadError,
)
from app.features.chat_integrations.models import (
    ChatConversationFlow,
)
from app.features.chat_integrations.providers.base import ChatDocumentDownloader
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.schemas import (
    ChatDocument,
    ChatDownloadedFile,
)
from app.features.chat_integrations.use_cases.action_tokens import ChatActionTokenBuilder
from app.features.imports.documents.commands.upload import (
    StatementUploadResult,
    StatementUploadUseCase,
)
from app.features.imports.documents.errors import UploadValidationError
from app.features.imports.parsers.extractors.resolver import SUPPORTED_STATEMENT_EXTENSIONS
from app.features.workspaces.service import WorkspaceContext

CHAT_DOCUMENT_UPLOAD_TTL = timedelta(minutes=30)
CHAT_DOCUMENT_UPLOAD_MAX_ACCOUNT_CHOICES = 8


@dataclass(frozen=True)
class ChatAccountChoice:
    name: str
    currency: str


@dataclass(frozen=True)
class StartedChatDocumentUpload:
    action_token: str
    account_choices: tuple[ChatAccountChoice, ...]


class ChatReviewUrlBuilder:
    @staticmethod
    def build_imports_url(settings: Settings | None) -> str | None:
        if settings is None or settings.public_base_url is None:
            return None
        return f"{settings.public_base_url.rstrip('/')}/imports"

    @staticmethod
    def build_document_review_url(
        settings: Settings | None,
        document_id: UUID,
    ) -> str | None:
        if settings is None or settings.public_base_url is None:
            return None
        base_url = settings.public_base_url.rstrip("/")
        return f"{base_url}/app/imports/documents/{document_id}/review"

    @staticmethod
    def build_raw_transaction_review_url(
        settings: Settings | None,
        *,
        document_id: UUID,
        raw_transaction_id: UUID,
    ) -> str | None:
        document_url = ChatReviewUrlBuilder.build_document_review_url(settings, document_id)
        if document_url is None:
            return None
        return f"{document_url}#raw-{raw_transaction_id}"


class ChatDocumentUploadService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        downloader: ChatDocumentDownloader,
    ) -> None:
        self.session = session
        self.settings = settings
        self.downloader = downloader
        self.accounts = AccountService(session)
        self.chat_integrations = ChatIntegrationRepository(session)

    async def start_document_upload(
        self,
        *,
        context: WorkspaceContext,
        document: ChatDocument | None,
    ) -> StartedChatDocumentUpload:
        if document is None:
            raise ChatDocumentUploadError("Document event does not include a file.")

        ChatDocumentUploadPolicy.ensure_supported_statement(
            document,
            max_bytes=self.settings.statement_upload_max_bytes,
        )
        accounts = await self.accounts.list_active_accounts(context.workspace.id)
        if not accounts:
            raise ChatDocumentUploadError("Create an account before uploading statements.")

        account_choices = tuple(
            ChatAccountChoice(name=account.name, currency=account.currency)
            for account in accounts[:CHAT_DOCUMENT_UPLOAD_MAX_ACCOUNT_CHOICES]
        )
        action_token = ChatActionTokenBuilder.build_token()
        await self.chat_integrations.create_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.UPLOAD_DOCUMENT,
            step="choose_account",
            action_token=action_token,
            state_payload={
                "file_id": document.file_id,
                "file_unique_id": document.file_unique_id,
                "file_name": document.file_name,
                "mime_type": document.mime_type,
                "file_size": document.file_size,
                "account_ids": [str(account.id) for account in accounts],
            },
            expires_at=utc_now() + CHAT_DOCUMENT_UPLOAD_TTL,
        )
        await self.session.commit()
        return StartedChatDocumentUpload(
            action_token=action_token,
            account_choices=account_choices,
        )

    async def complete_document_upload(
        self,
        *,
        context: WorkspaceContext,
        action_token: str,
        account_index: int,
    ) -> StatementUploadResult:
        state = await self.chat_integrations.get_active_conversation_state(
            workspace_id=context.workspace.id,
            user_id=context.user.id,
            flow=ChatConversationFlow.UPLOAD_DOCUMENT,
            action_token=action_token,
            now=utc_now(),
        )
        if state is None:
            raise ChatDocumentUploadError("This upload action expired. Send the statement again.")

        document = ChatDocumentUploadStateReader.read_document(state.state_payload)
        account_id = ChatDocumentUploadStateReader.read_account_id(
            state.state_payload,
            account_index,
        )
        downloaded_file = await self.downloader.download_document(document)
        upload_file = ChatDownloadedFileUploadAdapter.to_upload_file(downloaded_file)

        try:
            upload = await StatementUploadUseCase(
                self.session,
                self.settings,
            ).upload_statement(
                context=context,
                upload_file=upload_file,
                account_id=account_id,
                idempotency_key=state.id,
            )
        except UploadValidationError as exc:
            raise ChatDocumentUploadError(str(exc)) from exc
        await self.chat_integrations.consume_conversation_state(state, consumed_at=utc_now())
        await self.session.commit()
        return upload


class ChatDocumentUploadPolicy:
    @staticmethod
    def ensure_supported_statement(document: ChatDocument, *, max_bytes: int) -> None:
        if document.file_size is not None and document.file_size > max_bytes:
            raise ChatDocumentUploadError("Telegram statement file exceeds the upload size limit.")

        filename = document.file_name or ""
        extension = Path(filename).suffix.casefold()
        if extension not in SUPPORTED_STATEMENT_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_STATEMENT_EXTENSIONS))
            raise ChatDocumentUploadError(f"Only {allowed} statement files can be uploaded.")


class ChatDocumentUploadStateReader:
    @staticmethod
    def read_document(payload: dict[str, object]) -> ChatDocument:
        file_id = payload.get("file_id")
        if not isinstance(file_id, str) or not file_id:
            raise ChatDocumentUploadError("Stored upload state does not include a Telegram file.")

        return ChatDocument(
            file_id=file_id,
            file_unique_id=ChatDocumentUploadStateReader._optional_string(
                payload.get("file_unique_id")
            ),
            file_name=ChatDocumentUploadStateReader._optional_string(payload.get("file_name")),
            mime_type=ChatDocumentUploadStateReader._optional_string(payload.get("mime_type")),
            file_size=ChatDocumentUploadStateReader._optional_int(payload.get("file_size")),
        )

    @staticmethod
    def read_account_id(payload: dict[str, object], account_index: int) -> UUID:
        account_ids = payload.get("account_ids")
        if not isinstance(account_ids, list):
            raise ChatDocumentUploadError("Stored upload state does not include accounts.")
        if account_index < 0 or account_index >= len(account_ids):
            raise ChatDocumentUploadError("Selected account is no longer available.")

        account_id = account_ids[account_index]
        if not isinstance(account_id, str):
            raise ChatDocumentUploadError("Stored account id is invalid.")
        try:
            return UUID(account_id)
        except ValueError as exc:
            raise ChatDocumentUploadError("Stored account id is invalid.") from exc

    @staticmethod
    def _optional_string(value: object) -> str | None:
        return value if isinstance(value, str) else None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        return value if isinstance(value, int) else None


class ChatDownloadedFileUploadAdapter:
    @staticmethod
    def to_upload_file(downloaded_file: ChatDownloadedFile) -> UploadFile:
        headers = Headers({"content-type": downloaded_file.content_type or ""})
        return UploadFile(
            BytesIO(downloaded_file.file_bytes),
            size=len(downloaded_file.file_bytes),
            filename=downloaded_file.filename,
            headers=headers,
        )
