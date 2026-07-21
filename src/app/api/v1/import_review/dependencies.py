from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.imports.application.review.read_model import ImportReviewReader
from app.features.imports.repository import ImportRepository


def get_import_review_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewReader:
    return ImportReviewReader(ImportRepository(session))
