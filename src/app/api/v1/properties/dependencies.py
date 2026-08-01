from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.properties.application.directory import PropertyDirectoryService
from app.features.properties.repository import PropertyRepository


def get_property_directory_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PropertyDirectoryService:
    return PropertyDirectoryService(PropertyRepository(session))
