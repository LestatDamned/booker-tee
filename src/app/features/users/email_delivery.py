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


def build_password_reset_message(
    *,
    recipient: str,
    token: str,
    base_url: str,
) -> IdentityEmail:
    reset_url = f"{base_url.rstrip('/')}/app/auth/reset-password?{urlencode({'token': token})}"
    return IdentityEmail(
        recipient=recipient,
        subject="Восстановление пароля — Booker Tee",
        text=(
            "Используйте ссылку, чтобы задать новый пароль Booker Tee.\n\n"
            f"{reset_url}\n\n"
            "Ссылка действует 30 минут. Если вы не запрашивали восстановление, "
            "проигнорируйте письмо."
        ),
    )


def build_email_change_messages(
    *,
    current_email: str,
    target_email: str,
    token: str,
    base_url: str,
) -> tuple[IdentityEmail, IdentityEmail]:
    confirmation_url = f"{base_url.rstrip('/')}/app/profile/account?{urlencode({'token': token})}"
    return (
        IdentityEmail(
            recipient=current_email,
            subject="Запрошена смена email — Booker Tee",
            text=(
                "Для вашего аккаунта Booker Tee запрошена смена email.\n\n"
                "Текущий email останется прежним, пока новый адрес не будет подтверждён. "
                "Если это были не вы, смените пароль и завершите другие сессии."
            ),
        ),
        IdentityEmail(
            recipient=target_email,
            subject="Подтвердите новый email — Booker Tee",
            text=(
                "Подтвердите новый email для аккаунта Booker Tee.\n\n"
                f"{confirmation_url}\n\n"
                "Ссылка действует 30 минут и может быть использована один раз."
            ),
        ),
    )


def build_email_changed_message(*, recipient: str) -> IdentityEmail:
    return IdentityEmail(
        recipient=recipient,
        subject="Email аккаунта изменён — Booker Tee",
        text=(
            "Email вашего аккаунта Booker Tee был изменён. "
            "Если это были не вы, обратитесь к администратору сервиса."
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
