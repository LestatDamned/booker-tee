from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.accounts.application.directory import AccountDirectoryService
from app.features.accounts.repository import AccountRepository
from app.features.accounts.service import AccountService


def get_account_directory_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccountDirectoryService:
    return AccountDirectoryService(
        accounts=AccountRepository(session),
        creator=AccountService(session),
    )
