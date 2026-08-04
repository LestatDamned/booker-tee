import asyncio
import smtplib
import ssl
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.settings import Settings


@dataclass(frozen=True)
class IdentityEmail:
    recipient: str = field(repr=False)
    subject: str
    text: str = field(repr=False)


IdentityEmailSender = Callable[[IdentityEmail], Awaitable[None]]


def build_email_verification_message(
    *,
    recipient: str,
    token: str,
    base_url: str,
    next_path: str | None = None,
) -> IdentityEmail:
    query = {"token": token}
    if next_path is not None:
        query["next"] = next_path
    verification_url = f"{base_url.rstrip('/')}/app/auth/verify-email?{urlencode(query)}"
    return IdentityEmail(
        recipient=recipient,
        subject="Подтвердите email — Booker Tee",
        text=(
            "Подтвердите email, чтобы завершить регистрацию в Booker Tee.\n\n"
            f"{verification_url}\n\n"
            "Ссылка действует 24 часа. Если вы не регистрировались, проигнорируйте письмо."
        ),
    )


async def send_identity_email(message: IdentityEmail, settings: Settings) -> None:
    await asyncio.to_thread(_send_identity_email, message, settings)


async def discard_identity_email(_message: IdentityEmail) -> None:
    """Deliberate no-op for local/test environments with delivery disabled."""


def _send_identity_email(message: IdentityEmail, settings: Settings) -> None:
    if settings.smtp_host is None or settings.identity_email_from is None:
        raise RuntimeError("Identity email delivery is not configured.")

    email = EmailMessage()
    email["From"] = settings.identity_email_from
    email["To"] = message.recipient
    email["Subject"] = message.subject
    email.set_content(message.text)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username is not None and settings.smtp_password is not None:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(email)
