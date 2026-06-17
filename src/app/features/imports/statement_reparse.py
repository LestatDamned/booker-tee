from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.accounts.repository import AccountRepository
from app.features.imports.errors import ImportReparseError
from app.features.imports.extraction.pdfplumber_extractor import PdfPlumberExtractor
from app.features.imports.models import (
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.parse_attempts import (
    PARSER_EXCEPTIONS,
    create_running_parse_attempt,
    record_failed_parse_attempt,
)
from app.features.imports.parsers.factory import default_statement_parser_registry
from app.features.imports.processing import StatementParseProcessor
from app.features.imports.repository import ImportRepository
from app.features.workspaces.service import WorkspaceContext


class StatementReparseUseCase:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.accounts = AccountRepository(session)
        self.imports = ImportRepository(session)
        self.extractor = PdfPlumberExtractor()
        self.parse_processor = StatementParseProcessor(
            session=session,
            imports=self.imports,
            parser_registry=default_statement_parser_registry(),
        )

    async def reparse_document(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
    ) -> UploadedDocument:
        document = await self.imports.get_document_for_workspace(context.workspace.id, document_id)
        if document is None:
            raise ImportReparseError("Document was not found.")
        if any(row.status == RawTransactionStatus.CONFIRMED for row in document.raw_transactions):
            raise ImportReparseError("Documents with confirmed ledger rows cannot be reparsed.")

        attempt = await create_running_parse_attempt(
            self.imports,
            workspace_id=context.workspace.id,
            document_id=document.id,
        )
        await self.session.commit()

        try:
            extracted = self.extractor.extract(
                self.settings.upload_storage_dir / document.storage_key
            )
        except PARSER_EXCEPTIONS as exc:
            await record_failed_parse_attempt(
                self.imports,
                document,
                attempt,
                exc,
                document_status=UploadedDocumentStatus.REQUIRES_REVIEW,
            )
        else:
            await self.parse_processor.record_successful_attempt(
                document,
                attempt,
                extracted,
                currency=await self._selected_currency(context, document),
                exclude_duplicate_document_id=document.id,
                supersede_existing_rows=True,
            )

        await self.session.commit()
        reparsed_document = await self.imports.get_document_for_workspace(
            context.workspace.id,
            document_id,
        )
        if reparsed_document is None:
            raise ImportReparseError("Document was not found after reparse.")
        return reparsed_document

    async def _selected_currency(
        self,
        context: WorkspaceContext,
        document: UploadedDocument,
    ) -> str:
        if document.account_id is None:
            return context.workspace.default_currency
        account = await self.accounts.get_for_workspace(
            context.workspace.id,
            document.account_id,
        )
        if account is None:
            return context.workspace.default_currency
        return account.currency
