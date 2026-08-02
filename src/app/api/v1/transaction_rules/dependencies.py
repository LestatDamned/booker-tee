from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.transaction_rules.application.directory import (
    TransactionRuleDirectoryReader,
)
from app.features.transaction_rules.repository import TransactionRuleRepository


def get_transaction_rule_directory_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TransactionRuleDirectoryReader:
    return TransactionRuleDirectoryReader(TransactionRuleRepository(session))
