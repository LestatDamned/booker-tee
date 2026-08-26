import asyncio
import logging
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.imports.documents.attempts import (
    PARSER_EXCEPTIONS,
    create_running_parse_attempt,
    record_failed_parse_attempt,
)
from app.features.imports.documents.errors import (
    UploadAccountNotFoundError,
    UploadIdempotencyConflictError,
    UploadProcessingError,
    UploadTooLargeError,
    UploadValidationError,
)
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.storage import (
    StoredUpload,
    UploadStorage,
    sanitize_upload_filename,
)
from app.features.imports.documents.types import (
    ParseAttemptStatus,
    UploadedDocumentSource,
    UploadedDocumentStatus,
    UploadedDocumentType,
)
from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.models import (
    ParseAttempt,
    UploadedDocument,
)
from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.parsers.extractors.resolver import (
    SUPPORTED_STATEMENT_EXTENSIONS,
)
from app.features.imports.parsers.registry import StatementParserRegistry
from app.features.imports.parsers.sidecar.client import StatementParserSidecarClient
from app.features.imports.parsers.sidecar.protocol import (
    ParserSidecarError,
    ParserUnavailableError,
)
from app.features.imports.statements.process import StatementParseCompletionService
from app.features.imports.statements.repository import StatementRepository
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.errors import LedgerPostingError
from app.features.workspaces.activity_repository import WorkspaceActivityRepository
from app.features.workspaces.application.activity_details import (
    DocumentUploadedActivityDetails,
)
from app.features.workspaces.application.activity_writer import WorkspaceActivityWriter
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.service import WorkspaceContext
from app.shared.schemas import ApplicationModel

logger = logging.getLogger(__name__)
FAILURE_CLEANUP_TIMEOUT_SECONDS = 5.0


class StatementUploadResult(ApplicationModel):
    document_id: UUID
    document_status: UploadedDocumentStatus
    filename: str
    replayed: bool


class StatementUploadUseCase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.accounts = LedgerReferenceResolver(session)
        self.documents = DocumentRepository(session)
        self.mappings = MappingRepository(session)
        self.statements = StatementRepository(session)
        self.storage = UploadStorage(settings.upload_storage_dir)
        self.parser_client = StatementParserSidecarClient.from_settings(settings)
        self.parse_completion = StatementParseCompletionService(
            session=session,
            documents=self.documents,
            statements=self.statements,
            mappings=self.mappings,
            parser_registry=StatementParserRegistry.with_default_parsers(),
        )
        self.workspaces = WorkspaceRepository(session)
        self.activity = WorkspaceActivityWriter(WorkspaceActivityRepository(session))

    async def upload_statement(
        self,
        *,
        context: WorkspaceContext,
        upload_file: UploadFile,
        account_id: UUID,
        idempotency_key: UUID | None = None,
    ) -> StatementUploadResult:
        validate_statement_upload(upload_file)
        stored_upload: StoredUpload | None = None
        document_id: UUID | None = None
        attempt_id = uuid4()
        initial_commit_started = False
        try:
            try:
                account = await self.accounts.get_import_account(context.workspace.id, account_id)
            except LedgerPostingError as error:
                raise UploadAccountNotFoundError(
                    "Выбранный счёт недоступен в текущем пространстве."
                ) from error

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
                    return self._upload_result(existing, replayed=True)

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
                await self.activity.document_uploaded(
                    context=context,
                    document_id=document.id,
                    details=DocumentUploadedActivityDetails(
                        display_filename=sanitize_upload_filename(document.original_filename),
                    ),
                )
                initial_commit_started = True
                await self.session.commit()
            except IntegrityError:
                await self._rollback_pre_attempt_failure(stored_upload)
                existing = await self.documents.get_document_for_workspace(
                    context.workspace.id,
                    document_id,
                )
                if existing is not None and (
                    existing.account_id == account.id
                    and existing.original_filename == (upload_file.filename or "statement")
                    and existing.sha256_hash == stored_upload.sha256_hash
                ):
                    return self._upload_result(existing, replayed=True)
                raise UploadIdempotencyConflictError(
                    "Этот ключ повторной отправки уже использован для другого файла."
                ) from None
        except (
            UploadAccountNotFoundError,
            UploadIdempotencyConflictError,
            UploadTooLargeError,
            UploadValidationError,
        ):
            raise
        except asyncio.CancelledError as error:
            if initial_commit_started and stored_upload is not None and document_id is not None:
                try:
                    await self._reconcile_initial_commit_bounded(
                        workspace_id=context.workspace.id,
                        document_id=document_id,
                        attempt_id=attempt_id,
                        stored_upload=stored_upload,
                        error=error,
                    )
                except UploadProcessingError:
                    pass
            else:
                await self._rollback_pre_attempt_failure(stored_upload)
            raise
        except Exception as error:
            if initial_commit_started and stored_upload is not None and document_id is not None:
                await self._reconcile_initial_commit_bounded(
                    workspace_id=context.workspace.id,
                    document_id=document_id,
                    attempt_id=attempt_id,
                    stored_upload=stored_upload,
                    error=error,
                )
            else:
                await self._rollback_pre_attempt_failure(stored_upload)
            raise UploadProcessingError("Statement processing failed.") from None

        assert stored_upload is not None
        try:
            attempt = await create_running_parse_attempt(
                self.documents,
                workspace_id=context.workspace.id,
                document_id=document.id,
                attempt_id=attempt_id,
            )
            await self.session.commit()
        except asyncio.CancelledError as error:
            try:
                await self._commit_terminal_failure_if_persisted_bounded(
                    workspace_id=context.workspace.id,
                    document_id=document.id,
                    attempt_id=attempt_id,
                    error=error,
                )
            except UploadProcessingError:
                pass
            raise
        except Exception as error:
            await self._commit_terminal_failure_if_persisted_bounded(
                workspace_id=context.workspace.id,
                document_id=document.id,
                attempt_id=attempt_id,
                error=error,
            )
            raise UploadProcessingError("Statement processing failed.") from None

        extracted: ExtractedStatement | None = None
        try:
            extracted = await self._extract_statement(stored_upload.path)
            workspace = await self.workspaces.lock_for_update(context.workspace.id)
            if workspace is None or not workspace.is_active:
                await self.parse_completion.preserve_inactive_workspace_attempt(
                    document,
                    attempt,
                    extracted,
                )
            else:
                await self.parse_completion.complete_successful_attempt(
                    document,
                    attempt,
                    extracted,
                    currency=selected_currency,
                )
            await self.session.commit()
        except asyncio.CancelledError as error:
            try:
                await self._commit_terminal_failure_bounded(
                    workspace_id=context.workspace.id,
                    document_id=document.id,
                    attempt_id=attempt.id,
                    error=error,
                    extracted=extracted,
                )
            except UploadProcessingError:
                pass
            raise
        except (*PARSER_EXCEPTIONS, ParserSidecarError) as error:
            await self._commit_terminal_failure_bounded(
                workspace_id=context.workspace.id,
                document_id=document.id,
                attempt_id=attempt.id,
                error=error,
                extracted=extracted,
            )
            failed_document = await self.documents.get_document_for_workspace(
                context.workspace.id,
                document.id,
            )
            assert failed_document is not None
            return self._upload_result(failed_document, replayed=False)
        except Exception as error:
            await self._commit_terminal_failure_bounded(
                workspace_id=context.workspace.id,
                document_id=document.id,
                attempt_id=attempt.id,
                error=error,
                extracted=extracted,
            )
            raise UploadProcessingError("Statement processing failed.") from None
        await self._delete_processed_source(document, attempt, stored_upload)
        return self._upload_result(document, replayed=False)

    async def _rollback_pre_attempt_failure(
        self,
        stored_upload: StoredUpload | None,
    ) -> None:
        try:
            await self.session.rollback()
        except Exception as error:
            logger.error(
                "Statement pre-attempt rollback failed error_type=%s",
                type(error).__name__,
            )
        if stored_upload is None:
            return
        try:
            await self.storage.delete_stored_upload(stored_upload)
        except Exception as error:
            logger.error(
                "Statement pre-attempt source cleanup failed error_type=%s",
                type(error).__name__,
            )

    async def _reconcile_initial_commit_bounded(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        attempt_id: UUID,
        stored_upload: StoredUpload,
        error: BaseException,
    ) -> None:
        try:
            await asyncio.wait_for(
                self._reconcile_initial_commit(
                    workspace_id=workspace_id,
                    document_id=document_id,
                    attempt_id=attempt_id,
                    stored_upload=stored_upload,
                    error=error,
                ),
                timeout=FAILURE_CLEANUP_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.error("Statement initial commit reconciliation timed out")
            raise UploadProcessingError("Statement processing failed.") from None
        except Exception as reconciliation_error:
            logger.error(
                "Statement initial commit reconciliation failed error_type=%s",
                type(reconciliation_error).__name__,
            )
            raise UploadProcessingError("Statement processing failed.") from None

    async def _reconcile_initial_commit(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        attempt_id: UUID,
        stored_upload: StoredUpload,
        error: BaseException,
    ) -> None:
        await self.session.rollback()
        document = await self.documents.get_document_for_workspace(workspace_id, document_id)
        if document is None or document.storage_key != stored_upload.storage_key:
            await self.storage.delete_stored_upload(stored_upload)
            return
        attempt = await create_running_parse_attempt(
            self.documents,
            workspace_id=workspace_id,
            document_id=document_id,
            attempt_id=attempt_id,
        )
        await record_failed_parse_attempt(self.documents, document, attempt, error)
        await self.session.commit()

    async def _extract_statement(self, file_path: Path) -> ExtractedStatement:
        if self.parser_client is None:
            raise ParserUnavailableError("unavailable")
        return await self.parser_client.extract(file_path)

    async def _commit_terminal_failure(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        attempt_id: UUID,
        error: BaseException,
        extracted: ExtractedStatement | None,
    ) -> None:
        await self.session.rollback()
        document = await self.documents.get_document_for_workspace(workspace_id, document_id)
        attempt = await self.documents.get_parse_attempt_for_workspace(
            workspace_id,
            document_id,
            attempt_id,
        )
        if document is None or attempt is None:
            raise RuntimeError("Committed parse attempt could not be reloaded") from error
        if extracted is not None:
            await self.documents.store_attempt_extracted_raw(
                attempt,
                raw_text_by_page_json=extracted.text_by_page,
                raw_tables_json=[
                    {"page_number": page.page_number, "tables": page.tables}
                    for page in extracted.tables_by_page
                ],
                metadata=extracted.metadata,
            )
        await record_failed_parse_attempt(self.documents, document, attempt, error)
        await self.session.commit()

    async def _commit_terminal_failure_bounded(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        attempt_id: UUID,
        error: BaseException,
        extracted: ExtractedStatement | None,
    ) -> None:
        try:
            await asyncio.wait_for(
                self._commit_terminal_failure(
                    workspace_id=workspace_id,
                    document_id=document_id,
                    attempt_id=attempt_id,
                    error=error,
                    extracted=extracted,
                ),
                timeout=FAILURE_CLEANUP_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.error("Statement failure cleanup timed out")
            raise UploadProcessingError("Statement processing failed.") from None
        except Exception as cleanup_error:
            logger.error(
                "Statement failure cleanup failed error_type=%s",
                type(cleanup_error).__name__,
            )
            raise UploadProcessingError("Statement processing failed.") from None

    async def _commit_terminal_failure_if_persisted_bounded(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        attempt_id: UUID,
        error: BaseException,
    ) -> None:
        try:
            await asyncio.wait_for(
                self._commit_terminal_failure_if_persisted(
                    workspace_id=workspace_id,
                    document_id=document_id,
                    attempt_id=attempt_id,
                    error=error,
                ),
                timeout=FAILURE_CLEANUP_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.error("Statement failure cleanup timed out")
            raise UploadProcessingError("Statement processing failed.") from None
        except Exception as cleanup_error:
            logger.error(
                "Statement failure cleanup failed error_type=%s",
                type(cleanup_error).__name__,
            )
            raise UploadProcessingError("Statement processing failed.") from None

    async def _commit_terminal_failure_if_persisted(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        attempt_id: UUID,
        error: BaseException,
    ) -> None:
        await self.session.rollback()
        attempt = await self.documents.get_parse_attempt_for_workspace(
            workspace_id,
            document_id,
            attempt_id,
        )
        if attempt is None:
            return
        document = await self.documents.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise RuntimeError("Committed parse attempt document could not be reloaded") from error
        await record_failed_parse_attempt(self.documents, document, attempt, error)
        await self.session.commit()

    async def _delete_processed_source(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        stored_upload: StoredUpload,
    ) -> None:
        if should_retain_source_file(attempt):
            return
        try:
            await self.storage.delete_stored_upload(stored_upload)
        except OSError as error:
            logger.warning(
                "Processed upload source deletion failed error_type=%s",
                type(error).__name__,
            )
            return

        document.storage_key = None
        document.source_file_deleted_at = utc_now()
        await self.session.commit()

    @staticmethod
    def _upload_result(
        document: UploadedDocument,
        *,
        replayed: bool,
    ) -> StatementUploadResult:
        return StatementUploadResult(
            document_id=document.id,
            document_status=document.status,
            filename=document.original_filename,
            replayed=replayed,
        )

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


def should_retain_source_file(attempt: ParseAttempt) -> bool:
    if attempt.status not in {ParseAttemptStatus.SUCCESS, ParseAttemptStatus.REQUIRES_REVIEW}:
        return True
    validation_report = attempt.validation_report_json or {}
    return (
        validation_report.get("status") == "needs_mapping"
        or validation_report.get("source") == "visual_coordinate_mapping"
    )
