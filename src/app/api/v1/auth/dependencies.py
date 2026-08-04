from functools import partial
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.settings import Settings
from app.db.session import get_session
from app.features.users.email_delivery import (
    IdentityEmailSender,
    discard_identity_email,
    send_identity_email,
)
from app.features.users.email_verification import EmailVerificationService
from app.features.users.service import AuthenticationService


def get_authentication_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticationService:
    return AuthenticationService(session, settings)


def get_email_verification_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailVerificationService:
    return EmailVerificationService(session, settings)


def get_identity_email_sender(
    settings: Annotated[Settings, Depends(get_settings)],
) -> IdentityEmailSender:
    if not settings.identity_email_enabled:
        return discard_identity_email
    return partial(send_identity_email, settings=settings)
