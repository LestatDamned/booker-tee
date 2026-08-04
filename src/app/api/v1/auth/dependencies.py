from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.service import AuthenticationService


def get_authentication_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationService:
    return AuthenticationService(session, settings)
