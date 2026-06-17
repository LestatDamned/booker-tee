from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.imports.application.document_management import (
    ImportDocumentManagementUseCase,
    document_has_linked_operations,
)
from app.features.imports.application.review_status import (
    RawTransactionReviewStatusUseCase,
    raw_transaction_status_for_review_action,
)
from app.features.imports.application.statement_reparse import StatementReparseUseCase
from app.features.imports.application.statement_upload import (
    StatementUploadUseCase,
    validate_pdf_upload,
)
from app.features.imports.domain.deduplication import (
    mark_raw_transaction_duplicate,
    possible_duplicate_fingerprint,
)
from app.features.imports.errors import (
    ImportDocumentManagementError,
    ImportReparseError,
    RawTransactionReviewError,
    UploadValidationError,
)
from app.features.imports.mapping.dto import ImportDocumentDetailView, ImportViewMapper
from app.features.imports.models import (
    UploadedDocument,
)
from app.features.imports.query_repository import ImportQueryRepository
from app.features.workspaces.service import WorkspaceContext

__all__ = [
    "ImportDocumentManagementError",
    "ImportReparseError",
    "ImportService",
    "RawTransactionReviewError",
    "UploadValidationError",
    "document_has_linked_operations",
    "mark_raw_transaction_duplicate",
    "possible_duplicate_fingerprint",
    "raw_transaction_status_for_review_action",
    "validate_pdf_upload",
]


class ImportService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.queries = ImportQueryRepository(session)

    async def upload_and_extract_statement(
        self,
        *,
        context: WorkspaceContext,
        upload_file: UploadFile,
        account_id: UUID | None,
    ) -> UploadedDocument:
        return await StatementUploadUseCase(
            self.session,
            self.settings,
        ).upload_and_extract_statement(
            context=context,
            upload_file=upload_file,
            account_id=account_id,
        )

    async def list_documents(self, workspace_id: UUID) -> list[UploadedDocument]:
        return await self.queries.list_documents_for_workspace(workspace_id)

    async def get_document(self, workspace_id: UUID, document_id: UUID) -> UploadedDocument | None:
        return await self.queries.get_document_for_workspace(workspace_id, document_id)

    async def get_document_detail_view(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentDetailView | None:
        document = await self.queries.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return None
        return ImportViewMapper.document_detail_from_uploaded_document(document)

    async def reparse_document(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
    ) -> UploadedDocument:
        return await StatementReparseUseCase(self.session, self.settings).reparse_document(
            context=context,
            document_id=document_id,
        )

    async def set_raw_transaction_review_status(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        raw_transaction_id: UUID,
        action: str,
    ) -> UploadedDocument:
        return await RawTransactionReviewStatusUseCase(self.session).set_status(
            workspace_id=workspace_id,
            document_id=document_id,
            raw_transaction_id=raw_transaction_id,
            action=action,
        )

    async def ignore_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument:
        return await ImportDocumentManagementUseCase(self.session, self.settings).ignore_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )

    async def delete_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> None:
        await ImportDocumentManagementUseCase(self.session, self.settings).delete_document(
            workspace_id=workspace_id,
            document_id=document_id,
        )
