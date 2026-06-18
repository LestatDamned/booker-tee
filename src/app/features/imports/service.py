from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.mapping.dto import ImportDocumentDetailView, ImportViewMapper
from app.features.imports.models import (
    UploadedDocument,
)
from app.features.imports.query_repository import ImportQueryRepository


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.queries = ImportQueryRepository(session)

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
