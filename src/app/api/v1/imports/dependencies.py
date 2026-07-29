from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.imports.application.unknown_statement_mappings.import_use_case import (
    UnknownStatementMappingImportUseCase,
)
from app.features.imports.application.unknown_statement_mappings.reader import (
    UnknownStatementMappingReader,
)
from app.features.imports.documents.queries.detail import (
    ImportDocumentDetailReader,
)
from app.features.imports.documents.queries.list import ImportDocumentListReader
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.mapping.repository import MappingRepository


def get_import_document_list_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportDocumentListReader:
    return ImportDocumentListReader(DocumentRepository(session))


def get_import_document_detail_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportDocumentDetailReader:
    return ImportDocumentDetailReader(DocumentRepository(session))


def get_unknown_statement_mapping_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UnknownStatementMappingReader:
    return UnknownStatementMappingReader(
        DocumentRepository(session),
        MappingRepository(session),
    )


def get_unknown_statement_mapping_importer(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UnknownStatementMappingImportUseCase:
    return UnknownStatementMappingImportUseCase(session)
