from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.ledger.application.operations import OperationsReader


def get_operations_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OperationsReader:
    return OperationsReader(session)
