from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.accounts.repository import AccountRepository
from app.features.categories.application.detail import CategoryDetailReader
from app.features.categories.application.directory import CategoryDirectoryService
from app.features.categories.service import CategoryService
from app.features.ledger.repository import LedgerRepository
from app.features.transaction_rules.repository import TransactionRuleRepository


def get_category_directory_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CategoryDirectoryService:
    categories = CategoryService(session)
    return CategoryDirectoryService(source=categories, mutations=categories)


def get_category_detail_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CategoryDetailReader:
    return CategoryDetailReader(
        categories=CategoryService(session),
        currencies=AccountRepository(session),
        operations=LedgerRepository(session),
        rules=TransactionRuleRepository(session),
    )
