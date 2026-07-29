from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.imports.documents.queries.detail import (
    ImportDocumentDetailReader,
)
from app.features.imports.documents.queries.list import ImportDocumentListReader
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.mapping.commands.import_rows import (
    StatementMappingImportService,
)
from app.features.imports.mapping.queries.overview import (
    StatementMappingOverviewReader,
)
from app.features.imports.mapping.queries.preview import (
    StatementMappingPreviewReader,
)
from app.features.imports.mapping.queries.source_rows import (
    StatementMappingSourceRowsReader,
)
from app.features.imports.mapping.repository import MappingRepository


def get_import_document_list_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportDocumentListReader:
    return ImportDocumentListReader(DocumentRepository(session))


def get_import_document_detail_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportDocumentDetailReader:
    return ImportDocumentDetailReader(DocumentRepository(session))


def get_statement_mapping_overview_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatementMappingOverviewReader:
    return StatementMappingOverviewReader(
        DocumentRepository(session),
        MappingRepository(session),
    )


def get_statement_mapping_preview_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatementMappingPreviewReader:
    return StatementMappingPreviewReader(DocumentRepository(session))


def get_statement_mapping_source_rows_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatementMappingSourceRowsReader:
    return StatementMappingSourceRowsReader(DocumentRepository(session))


def get_statement_mapping_importer(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StatementMappingImportService:
    return StatementMappingImportService(session)
