"""Create categories from the import-review workflow."""

from typing import Protocol
from uuid import UUID

from app.features.categories.models import Category, CategoryKind
from app.features.import_review.application.queries.classification import (
    ImportReviewCategoryReferenceDto,
    category_reference_dto,
)
from app.features.imports.models import UploadedDocument


class ImportReviewCategoryDocumentSource(Protocol):
    async def get_document_for_workspace(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument | None: ...


class ImportReviewCategoryWriter(Protocol):
    async def create_custom(
        self,
        *,
        workspace_id: UUID,
        name: str,
        kind: CategoryKind,
        notes: str | None = None,
    ) -> Category: ...


class ImportReviewCategoryCreator:
    def __init__(
        self,
        documents: ImportReviewCategoryDocumentSource,
        categories: ImportReviewCategoryWriter,
    ) -> None:
        self._documents = documents
        self._categories = categories

    async def create(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        item_id: UUID,
        name: str,
        kind: CategoryKind,
    ) -> ImportReviewCategoryReferenceDto | None:
        document = await self._documents.get_document_for_workspace(workspace_id, document_id)
        if document is None or not any(row.id == item_id for row in document.raw_transactions):
            return None
        category = await self._categories.create_custom(
            workspace_id=workspace_id,
            name=name,
            kind=kind,
        )
        return category_reference_dto(category)
