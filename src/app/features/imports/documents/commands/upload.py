from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.accounts.repository import AccountRepository
from app.features.imports.documents.attempts import (
    PARSER_EXCEPTIONS,
    create_running_parse_attempt,
    record_failed_parse_attempt,
)
from app.features.imports.documents.errors import (
    UploadAccountNotFoundError,
    UploadIdempotencyConflictError,
    UploadValidationError,
)
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.storage import UploadStorage
from app.features.imports.documents.types import (
    UploadedDocumentSource,
    UploadedDocumentStatus,
    UploadedDocumentType,
)
from app.features.imports.infrastructure.extraction.resolver import (
    SUPPORTED_STATEMENT_EXTENSIONS,
    StatementExtractorResolver,
)
from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.models import (
    UploadedDocument,
)
from app.features.imports.parsing.registry import default_statement_parser_registry
from app.features.imports.statements.process import StatementParseCompletionService
from app.features.imports.statements.repository import StatementRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class StatementUploadResult:
    document: UploadedDocument
    replayed: bool


class StatementUploadUseCase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.accounts = AccountRepository(session)
        self.documents = DocumentRepository(session)
        self.mappings = MappingRepository(session)
        self.statements = StatementRepository(session)
        self.storage = UploadStorage(settings.upload_storage_dir)
        self.extractor = StatementExtractorResolver()
        self.parse_completion = StatementParseCompletionService(
            session=session,
            documents=self.documents,
            statements=self.statements,
            mappings=self.mappings,
            parser_registry=default_statement_parser_registry(),
        )

    async def upload_and_extract_statement(
        self,
        *,
        context: WorkspaceContext,
        upload_file: UploadFile,
        account_id: UUID,
    ) -> UploadedDocument:
        result = await self.upload_statement(
            context=context,
            upload_file=upload_file,
            account_id=account_id,
        )
        return result.document

    async def upload_statement(
        self,
        *,
        context: WorkspaceContext,
        upload_file: UploadFile,
        account_id: UUID,
        idempotency_key: UUID | None = None,
    ) -> StatementUploadResult:
        validate_statement_upload(upload_file)
        account = await self.accounts.get_for_workspace(context.workspace.id, account_id)
        if account is None:
            raise UploadAccountNotFoundError("Выбранный счёт недоступен в текущем пространстве.")

        document_id = (
            uuid5(context.workspace.id, f"statement-upload:{idempotency_key}")
            if idempotency_key is not None
            else uuid4()
        )
        if idempotency_key is not None:
            existing = await self.documents.get_document_for_workspace(
                context.workspace.id,
                document_id,
            )
            if existing is not None:
                digest, _ = await self.storage.inspect_upload(
                    upload_file,
                    max_bytes=self.settings.statement_upload_max_bytes,
                )
                if (
                    existing.account_id != account.id
                    or existing.original_filename != (upload_file.filename or "statement")
                    or existing.sha256_hash != digest
                ):
                    raise UploadIdempotencyConflictError(
                        "Этот ключ повторной отправки уже использован для другого файла."
                    )
                return StatementUploadResult(document=existing, replayed=True)

        stored_upload = await self.storage.save_upload(
            upload_file,
            workspace_id=context.workspace.id,
            document_id=uuid4() if idempotency_key is not None else document_id,
            max_bytes=self.settings.statement_upload_max_bytes,
        )
        selected_currency = account.currency
        try:
            document = await self._create_document(
                context=context,
                document_id=document_id,
                upload_file=upload_file,
                stored_path=stored_upload.path,
                storage_key=stored_upload.storage_key,
                sha256_hash=stored_upload.sha256_hash,
                file_size_bytes=stored_upload.file_size_bytes,
                account_id=account.id,
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            await self.storage.delete_stored_upload(stored_upload)
            existing = await self.documents.get_document_for_workspace(
                context.workspace.id,
                document_id,
            )
            if existing is not None and (
                existing.account_id == account.id
                and existing.original_filename == (upload_file.filename or "statement")
                and existing.sha256_hash == stored_upload.sha256_hash
            ):
                return StatementUploadResult(document=existing, replayed=True)
            raise UploadIdempotencyConflictError(
                "Этот ключ повторной отправки уже использован для другого файла."
            ) from error

        attempt = await create_running_parse_attempt(
            self.documents,
            workspace_id=context.workspace.id,
            document_id=document.id,
        )
        await self.session.commit()

        try:
            extracted = self.extractor.extract(stored_upload.path)
        except PARSER_EXCEPTIONS as exc:
            await record_failed_parse_attempt(self.documents, document, attempt, exc)
        else:
            await self.parse_completion.complete_successful_attempt(
                document,
                attempt,
                extracted,
                currency=selected_currency,
            )

        await self.session.commit()
        return StatementUploadResult(document=document, replayed=False)

    async def _create_document(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        upload_file: UploadFile,
        stored_path: Path,
        storage_key: str,
        sha256_hash: str,
        file_size_bytes: int,
        account_id: UUID | None,
    ) -> UploadedDocument:
        document = UploadedDocument(
            id=document_id,
            workspace_id=context.workspace.id,
            source=UploadedDocumentSource.WEB_UPLOAD,
            document_type=UploadedDocumentType.BANK_STATEMENT,
            status=UploadedDocumentStatus.UPLOADED,
            original_filename=upload_file.filename or stored_path.name,
            storage_key=storage_key,
            content_type=upload_file.content_type,
            file_size_bytes=file_size_bytes,
            sha256_hash=sha256_hash,
            uploaded_by_user_id=context.user.id,
            account_id=account_id,
        )
        return await self.documents.create_uploaded_document(document)


def validate_statement_upload(upload_file: UploadFile) -> None:
    filename = upload_file.filename or ""
    if Path(filename).suffix.casefold() not in SUPPORTED_STATEMENT_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_STATEMENT_EXTENSIONS))
        raise UploadValidationError(f"Only {allowed} statement files can be uploaded.")
