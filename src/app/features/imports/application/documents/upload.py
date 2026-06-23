from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.accounts.repository import AccountRepository
from app.features.imports.application.documents.parse_attempts import (
    PARSER_EXCEPTIONS,
    create_running_parse_attempt,
    record_failed_parse_attempt,
)
from app.features.imports.application.processing import StatementParseProcessor
from app.features.imports.errors import UploadValidationError
from app.features.imports.infrastructure.extraction.resolver import (
    SUPPORTED_STATEMENT_EXTENSIONS,
    StatementExtractorResolver,
)
from app.features.imports.infrastructure.storage import UploadStorage
from app.features.imports.models import (
    UploadedDocument,
    UploadedDocumentSource,
    UploadedDocumentStatus,
    UploadedDocumentType,
)
from app.features.imports.parsing.registry import default_statement_parser_registry
from app.features.imports.repository import ImportRepository
from app.features.workspaces.service import WorkspaceContext


class StatementUploadUseCase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.accounts = AccountRepository(session)
        self.imports = ImportRepository(session)
        self.storage = UploadStorage(settings.upload_storage_dir)
        self.extractor = StatementExtractorResolver()
        self.parse_processor = StatementParseProcessor(
            session=session,
            imports=self.imports,
            parser_registry=default_statement_parser_registry(),
        )

    async def upload_and_extract_statement(
        self,
        *,
        context: WorkspaceContext,
        upload_file: UploadFile,
        account_id: UUID,
    ) -> UploadedDocument:
        validate_statement_upload(upload_file)
        account = await self.accounts.get_for_workspace(context.workspace.id, account_id)
        if account is None:
            raise UploadValidationError("Selected account is not available in this workspace.")

        document_id = uuid4()
        stored_upload = await self.storage.save_upload(
            upload_file,
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
        selected_currency = account.currency
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

        attempt = await create_running_parse_attempt(
            self.imports,
            workspace_id=context.workspace.id,
            document_id=document.id,
        )
        await self.session.commit()

        try:
            extracted = self.extractor.extract(stored_upload.path)
        except PARSER_EXCEPTIONS as exc:
            await record_failed_parse_attempt(self.imports, document, attempt, exc)
        else:
            await self.parse_processor.record_successful_attempt(
                document,
                attempt,
                extracted,
                currency=selected_currency,
            )

        await self.session.commit()
        return document

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
        return await self.imports.create_uploaded_document(document)


def validate_statement_upload(upload_file: UploadFile) -> None:
    filename = upload_file.filename or ""
    if Path(filename).suffix.casefold() not in SUPPORTED_STATEMENT_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_STATEMENT_EXTENSIONS))
        raise UploadValidationError(f"Only {allowed} statement files can be uploaded.")


def validate_pdf_upload(upload_file: UploadFile) -> None:
    validate_statement_upload(upload_file)
