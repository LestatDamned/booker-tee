from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.imports.application.documents.listing import ImportDocumentListReader
from app.features.imports.query_repository import ImportQueryRepository


def get_import_document_list_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportDocumentListReader:
    return ImportDocumentListReader(ImportQueryRepository(session))
