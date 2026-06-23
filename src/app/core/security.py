"""Security helpers for authentication and authorization."""

from hashlib import sha256
from hmac import compare_digest, new
from secrets import token_urlsafe

from fastapi import Request
from fastapi.responses import Response
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.settings import Settings

_PASSWORD_HASHER = PasswordHash.recommended()
SESSION_TOKEN_BYTES = 32
CSRF_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password, password_hash)
    except UnknownHashError:
        return False


def generate_session_token() -> str:
    return token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(session_token: str) -> str:
    return sha256(session_token.encode("utf-8")).hexdigest()


def csrf_token_for_session(session_token: str, settings: Settings) -> str:
    digest = new(
        settings.auth_secret_key.encode("utf-8"),
        session_token.encode("utf-8"),
        sha256,
    ).hexdigest()
    return digest


def verify_csrf_token(
    *,
    provided_token: str | None,
    session_token: str,
    settings: Settings,
) -> bool:
    if not provided_token:
        return False
    expected_token = csrf_token_for_session(session_token, settings)
    return compare_digest(provided_token, expected_token)


def session_token_from_request(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def remember_session(response: Response, *, settings: Settings, session_token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def forget_session(response: Response, *, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
