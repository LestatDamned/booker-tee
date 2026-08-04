from hashlib import sha256
from hmac import new
from secrets import token_urlsafe
from uuid import UUID

INVITATION_TOKEN_BYTES = 32


def generate_invitation_token() -> str:
    return token_urlsafe(INVITATION_TOKEN_BYTES)


def hash_invitation_token(invitation_token: str) -> str:
    return sha256(invitation_token.encode("utf-8")).hexdigest()


def invitation_token_for_id(*, invitation_id: UUID, secret: str) -> str:
    return new(
        secret.encode("utf-8"),
        f"workspace-invitation:{invitation_id}".encode(),
        sha256,
    ).hexdigest()
