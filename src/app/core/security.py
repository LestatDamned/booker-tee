"""Security helpers for authentication and authorization."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest, new
from secrets import token_urlsafe
from uuid import UUID

import jwt
from fastapi import Request
from fastapi.responses import Response
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.settings import Settings

_PASSWORD_HASHER = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("booker-tee-dummy-password")
TOKEN_RANDOM_BYTES = 32
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "booker-tee"
JWT_AUDIENCE = "booker-tee-api"


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    session_id: UUID
    token_id: str


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password, password_hash)
    except UnknownHashError:
        return False


def verify_and_update_password(password: str, password_hash: str) -> tuple[bool, str | None]:
    try:
        return _PASSWORD_HASHER.verify_and_update(password, password_hash)
    except UnknownHashError:
        return False, None


def verify_dummy_password(password: str) -> None:
    _PASSWORD_HASHER.verify(password, _DUMMY_PASSWORD_HASH)


def generate_token_pair(
    *,
    user_id: UUID,
    session_id: UUID,
    refresh_expires_at: datetime,
    settings: Settings,
) -> TokenPair:
    now = datetime.now(UTC)
    common = {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": now,
    }
    access_token = jwt.encode(
        {
            **common,
            "exp": now + timedelta(seconds=settings.access_token_max_age_seconds),
            "jti": token_urlsafe(TOKEN_RANDOM_BYTES),
            "type": "access",
        },
        settings.auth_secret_key,
        algorithm=JWT_ALGORITHM,
    )
    refresh_token = jwt.encode(
        {
            **common,
            "exp": refresh_expires_at,
            "jti": token_urlsafe(TOKEN_RANDOM_BYTES),
            "type": "refresh",
        },
        settings.auth_secret_key,
        algorithm=JWT_ALGORITHM,
    )
    return TokenPair(access_token, refresh_token, settings.access_token_max_age_seconds)


def decode_access_token(token: str, settings: Settings) -> TokenClaims | None:
    return _decode_token(token, expected_type="access", settings=settings)


def decode_refresh_token(token: str, settings: Settings) -> TokenClaims | None:
    return _decode_token(token, expected_type="refresh", settings=settings)


def _decode_token(token: str, *, expected_type: str, settings: Settings) -> TokenClaims | None:
    for secret in (settings.auth_secret_key, *settings.auth_previous_secret_keys):
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[JWT_ALGORITHM],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
                options={"require": ["sub", "sid", "exp", "iat", "jti", "type"]},
            )
            if payload["type"] != expected_type:
                return None
            return TokenClaims(
                user_id=UUID(payload["sub"]),
                session_id=UUID(payload["sid"]),
                token_id=payload["jti"],
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            continue
    return None


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


# Compatibility name for application code being migrated from opaque sessions.
hash_session_token = hash_token


def generate_user_token() -> str:
    return token_urlsafe(TOKEN_RANDOM_BYTES)


def hash_user_token(user_token: str) -> str:
    return hash_token(user_token)


def auth_rate_limit_bucket_hash(*, scope: str, key: str, settings: Settings) -> str:
    return new(
        settings.auth_secret_key.encode("utf-8"),
        f"{scope}\0{key}".encode(),
        sha256,
    ).hexdigest()


def csrf_token_for_session(session_id: UUID | str, settings: Settings) -> str:
    return new(
        settings.auth_secret_key.encode("utf-8"),
        str(session_id).encode("utf-8"),
        sha256,
    ).hexdigest()


def verify_csrf_token(
    *,
    provided_token: str | None,
    settings: Settings,
    session_id: UUID | str | None = None,
    session_token: str | None = None,
) -> bool:
    if not provided_token:
        return False
    binding = session_id if session_id is not None else session_token
    if binding is None:
        return False
    return compare_digest(provided_token, csrf_token_for_session(binding, settings))


def bearer_token_from_request(request: Request) -> str | None:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" and token else None


def refresh_token_from_request(request: Request, settings: Settings) -> str | None:
    return request.cookies.get(settings.refresh_cookie_name)


session_token_from_request = refresh_token_from_request


def remember_refresh_token(response: Response, *, settings: Settings, refresh_token: str) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh_token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )
    response.headers["Cache-Control"] = "no-store"


def forget_refresh_token(response: Response, *, settings: Settings) -> None:
    response.delete_cookie(
        settings.refresh_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )
    response.headers["Cache-Control"] = "no-store"
