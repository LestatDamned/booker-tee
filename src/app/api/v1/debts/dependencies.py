from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.debts.reader import DebtReader
from app.features.debts.repository import DebtRepository
from app.features.debts.service import DebtService


def get_debt_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DebtReader:
    return DebtReader(DebtRepository(session))


def get_debt_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DebtService:
    return DebtService(session)
