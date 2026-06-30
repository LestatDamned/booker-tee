from hashlib import sha256
from secrets import token_urlsafe

INVITATION_TOKEN_BYTES = 32


def generate_invitation_token() -> str:
    return token_urlsafe(INVITATION_TOKEN_BYTES)


def hash_invitation_token(invitation_token: str) -> str:
    return sha256(invitation_token.encode("utf-8")).hexdigest()
