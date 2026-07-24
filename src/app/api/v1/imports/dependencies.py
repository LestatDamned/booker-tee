from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.imports.application.documents.detail_reading import (
    ImportDocumentDetailReader,
)
from app.features.imports.application.documents.listing import ImportDocumentListReader
from app.features.imports.application.unknown_statement_mappings.import_use_case import (
    UnknownStatementMappingImportUseCase,
)
from app.features.imports.application.unknown_statement_mappings.reader import (
    UnknownStatementMappingReader,
)
from app.features.imports.application.unknown_statement_mappings.template_use_case import (
    UnknownStatementMappingTemplateUseCase,
)
from app.features.imports.query_repository import ImportQueryRepository
from app.features.imports.service import ImportService


def get_import_document_list_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportDocumentListReader:
    return ImportDocumentListReader(ImportQueryRepository(session))


def get_import_document_detail_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportDocumentDetailReader:
    return ImportDocumentDetailReader(ImportService(session))


def get_unknown_statement_mapping_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UnknownStatementMappingReader:
    return UnknownStatementMappingReader(
        ImportService(session),
        UnknownStatementMappingTemplateUseCase(session),
    )


def get_unknown_statement_mapping_importer(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UnknownStatementMappingImportUseCase:
    return UnknownStatementMappingImportUseCase(session)
