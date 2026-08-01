from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.categories.application.directory import CategoryDirectoryService
from app.features.categories.service import CategoryService


def get_category_directory_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CategoryDirectoryService:
    categories = CategoryService(session)
    return CategoryDirectoryService(source=categories, mutations=categories)
