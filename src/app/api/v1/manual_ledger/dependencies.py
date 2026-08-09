from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.features.categories.service import CategoryService
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.manual_operations import (
    ManualLedgerReferenceReader,
    ManualOperationService,
)
from app.features.properties.service import PropertyService


def get_manual_operation_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ManualOperationService:
    return ManualOperationService(session)


def get_manual_ledger_reference_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ManualLedgerReferenceReader:
    return ManualLedgerReferenceReader(
        accounts=LedgerReferenceResolver(session),
        categories=CategoryService(session),
        properties=PropertyService(session),
    )
