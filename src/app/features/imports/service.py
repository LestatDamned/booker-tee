from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.documents.detail_view import (
    ImportDocumentDetailView,
    ImportDocumentDetailViewMapper,
)
from app.features.imports.models import (
    UploadedDocument,
)
from app.features.imports.query_repository import ImportQueryRepository


class ImportService:
    def __init__(self, session: AsyncSession) -> None:
        self.queries = ImportQueryRepository(session)

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
        return ImportDocumentDetailViewMapper.from_uploaded_document(document)
