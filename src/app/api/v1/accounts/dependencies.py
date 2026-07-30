from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.accounts.application.directory import AccountDirectoryService
from app.features.accounts.repository import AccountRepository
from app.features.accounts.service import AccountService
from app.features.ledger.application.account_ledger import AccountLedgerReader


def get_account_directory_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccountDirectoryService:
    return AccountDirectoryService(
        accounts=AccountRepository(session),
        creator=AccountService(session),
    )


def get_account_ledger_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccountLedgerReader:
    return AccountLedgerReader(session)
