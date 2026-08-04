from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.account_deactivation import AccountDeactivationService
from app.features.users.email_change import EmailChangeService
from app.features.users.service import UserService
from app.features.users.sessions import UserSessionService


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserService:
    return UserService(session)


def get_user_session_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserSessionService:
    return UserSessionService(session, settings)


def get_email_change_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailChangeService:
    return EmailChangeService(session, settings)


def get_account_deactivation_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AccountDeactivationService:
    return AccountDeactivationService(session)
