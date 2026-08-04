from dataclasses import dataclass
from uuid import uuid4

from api_client import ApiTestClient as TestClient
from app.api.dependencies import (
    AuthenticatedSessionContext,
    get_authenticated_session_context,
)
from app.api.v1.account.dependencies import get_user_service
from app.api.v1.auth.dependencies import (
    get_authentication_service,
    get_email_verification_service,
    get_identity_email_sender,
)
from app.core.config import get_settings
from app.core.settings import Settings
from app.features.users.email_delivery import IdentityEmail
from app.features.users.email_verification import VerificationRequest
from app.features.users.errors import InvalidCredentialsError, SignupsClosedError
from app.features.users.models import User, UserSession
from app.main import create_app

SAME_ORIGIN_HEADERS = {"Origin": "http://testserver"}


@dataclass
class AuthenticationStub:
    error: Exception | None = None
    session_token: str = "opaque-session-token"
    logged_out_token: str | None = None

    async def login(self, **_values: object) -> object:
        if self.error:
            raise self.error
        return _LoginResult(self.session_token)

    async def logout(self, session_token: str) -> None:
        self.logged_out_token = session_token


@dataclass
class _LoginResult:
    session_token: str


@dataclass
class EmailVerificationStub:
    error: Exception | None = None
    email: IdentityEmail | None = None
    session_token: str = "verified-session-token"

    async def request_signup(self, **_values: object) -> VerificationRequest:
        if self.error:
            raise self.error
        return VerificationRequest(email=self.email)

    async def request_resend(self, **_values: object) -> VerificationRequest:
        if self.error:
            raise self.error
        return VerificationRequest(email=self.email)

    async def verify(self, **_values: object) -> object:
        if self.error:
            raise self.error
        return _LoginResult(self.session_token)


class UserServiceStub:
    async def update_name(self, *, user: User, name: str | None) -> User:
        user.name = name.strip() if name and name.strip() else None
        return user


def test_auth_config_exposes_signup_availability() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test",
        allow_signups=False,
        password_min_length=12,
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/config")

    assert response.status_code == 200
    assert response.json() == {
        "allowSignups": False,
        "passwordMinLength": 12,
    }


def test_login_sets_http_only_cookie_and_preserves_safe_next() -> None:
    app = create_app()
    authentication = AuthenticationStub()
    app.dependency_overrides[get_authentication_service] = lambda: authentication

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers=SAME_ORIGIN_HEADERS,
            json={
                "email": "max@example.test",
                "password": "correct horse battery staple",
                "nextPath": "/workspaces/invitations/example",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"nextPath": "/workspaces/invitations/example"}
    cookie = response.headers["set-cookie"]
    assert "booker_session=opaque-session-token" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_login_rejects_external_next_and_invalid_credentials() -> None:
    app = create_app()
    authentication = AuthenticationStub(error=InvalidCredentialsError("Неверный email или пароль."))
    app.dependency_overrides[get_authentication_service] = lambda: authentication

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers=SAME_ORIGIN_HEADERS,
            json={
                "email": "max@example.test",
                "password": "wrong-password",
                "nextPath": "https://evil.example",
            },
        )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "invalid_credentials",
            "message": "Неверный email или пароль.",
        }
    }


def test_signup_reports_closed_registration() -> None:
    app = create_app()
    verification = EmailVerificationStub(error=SignupsClosedError("closed"))
    app.dependency_overrides[get_email_verification_service] = lambda: verification

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/signup",
            headers=SAME_ORIGIN_HEADERS,
            json={"email": "max@example.test", "password": "long-enough"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "signups_closed"


def test_signup_returns_generic_accepted_response_without_session_cookie() -> None:
    app = create_app()
    sent: list[IdentityEmail] = []
    message = IdentityEmail(
        recipient="max@example.test",
        subject="Подтвердите email",
        text="verification link",
    )
    app.dependency_overrides[get_email_verification_service] = lambda: EmailVerificationStub(
        email=message
    )

    async def capture_email(email: IdentityEmail) -> None:
        sent.append(email)

    app.dependency_overrides[get_identity_email_sender] = lambda: capture_email

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/signup",
            headers=SAME_ORIGIN_HEADERS,
            json={"email": "max@example.test", "password": "long-enough"},
        )

    assert response.status_code == 202
    assert response.json() == {
        "message": "Если адрес подходит для регистрации, мы отправили письмо с подтверждением.",
        "retryAfterSeconds": 60,
    }
    assert "booker_session" not in response.headers.get("set-cookie", "")
    assert sent == [message]


def test_email_verification_sets_session_cookie_and_safe_continuation() -> None:
    app = create_app()
    app.dependency_overrides[get_email_verification_service] = lambda: EmailVerificationStub()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/email-verifications",
            headers=SAME_ORIGIN_HEADERS,
            json={"token": "opaque-token", "nextPath": "https://evil.example"},
        )

    assert response.status_code == 200
    assert response.json() == {"nextPath": "/app/workspaces"}
    assert "booker_session=verified-session-token" in response.headers["set-cookie"]


def test_legacy_signup_redirects_to_react_and_preserves_continuation() -> None:
    with TestClient(create_app(), follow_redirects=False) as client:
        response = client.get("/signup?next=/workspaces/invitations/example")

    assert response.status_code == 307
    assert response.headers["location"] == ("/app/auth/signup?next=/workspaces/invitations/example")


def test_successful_login_rejects_external_next() -> None:
    app = create_app()
    app.dependency_overrides[get_authentication_service] = lambda: AuthenticationStub()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers=SAME_ORIGIN_HEADERS,
            json={
                "email": "max@example.test",
                "password": "long-enough",
                "nextPath": "//evil.example",
            },
        )

    assert response.json() == {"nextPath": "/app/workspaces"}


def test_public_auth_mutations_reject_missing_and_cross_site_origin() -> None:
    app = create_app()
    app.dependency_overrides[get_authentication_service] = lambda: AuthenticationStub()
    payload = {"email": "max@example.test", "password": "long-enough"}

    with TestClient(app) as client:
        missing = client.post("/api/v1/auth/login", json=payload)
        cross_site = client.post(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://evil.example",
                "Sec-Fetch-Site": "cross-site",
            },
            json=payload,
        )

    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "invalid_origin"
    assert cross_site.status_code == 403
    assert cross_site.json()["error"]["code"] == "invalid_origin"


def test_public_auth_mutation_accepts_same_origin_fetch_metadata() -> None:
    app = create_app()
    app.dependency_overrides[get_authentication_service] = lambda: AuthenticationStub()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            headers={"Sec-Fetch-Site": "same-origin"},
            json={"email": "max@example.test", "password": "long-enough"},
        )

    assert response.status_code == 200


def test_account_reads_and_updates_without_workspace_context() -> None:
    app = create_app()
    context = _account_context()
    app.dependency_overrides[get_authenticated_session_context] = lambda: context
    app.dependency_overrides[get_user_service] = lambda: UserServiceStub()

    with TestClient(app) as client:
        read_response = client.get("/api/v1/account")
        update_response = client.patch(
            "/api/v1/account",
            json={"name": "  Maxim  "},
        )

    assert read_response.status_code == 200
    assert read_response.json()["email"] == "max@example.test"
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Maxim"


def test_account_requires_authentication() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/account")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_logout_revokes_server_session_and_clears_cookie() -> None:
    app = create_app()
    authentication = AuthenticationStub()
    app.dependency_overrides[get_authenticated_session_context] = _account_context
    app.dependency_overrides[get_authentication_service] = lambda: authentication

    with TestClient(app) as client:
        response = client.delete("/api/v1/auth/session")

    assert response.status_code == 204
    assert authentication.logged_out_token == "opaque-session-token"
    assert "booker_session=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def _account_context() -> AuthenticatedSessionContext:
    user = User(
        id=uuid4(),
        email="max@example.test",
        name="Max",
        password_hash="hash",
    )
    user_session = UserSession(
        id=uuid4(),
        user_id=user.id,
        session_token_hash="hash",
        expires_at=user.created_at,
    )
    return AuthenticatedSessionContext(
        user=user,
        session=user_session,
        csrf_token="csrf-token",
        session_token="opaque-session-token",
    )
