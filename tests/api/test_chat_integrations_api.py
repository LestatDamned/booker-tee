from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from api_client import ApiTestClient as TestClient
from app.api.dependencies import get_api_request_context
from app.api.errors import install_api_exception_handlers
from app.api.v1.chat_integrations.router import (
    get_chat_identity_binder,
    get_telegram_link_code_issuer,
    router,
)
from app.core.config import get_settings
from app.core.security import csrf_token_for_session
from app.core.settings import Settings
from app.features.chat_integrations.actions.identity import BindChatIdentityCommand
from app.features.chat_integrations.errors import ChatIdentityBindingError
from app.features.chat_integrations.use_cases.identity import TelegramLinkCode
from app.features.workspaces.domain.types import WorkspaceRole


class ChatIdentityBinderStub:
    def __init__(self) -> None:
        self.commands: list[BindChatIdentityCommand] = []
        self.error: ChatIdentityBindingError | None = None

    async def bind_chat_identity(self, command: BindChatIdentityCommand) -> object:
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        return object()


class TelegramLinkCodeIssuerStub:
    def __init__(self) -> None:
        self.calls = 0

    async def issue(self, context: object) -> TelegramLinkCode:
        del context
        self.calls += 1
        return TelegramLinkCode(
            code="workspace-id.secret",
            expires_at=datetime(2026, 8, 29, 12, 0, tzinfo=UTC),
        )


def chat_integrations_app(
    *, environment: Literal["local", "test", "production"] = "local"
) -> tuple[FastAPI, ChatIdentityBinderStub]:
    app = FastAPI()
    install_api_exception_handlers(app)
    app.include_router(router, prefix="/api/v1")
    settings = Settings(
        environment=environment,
        debug=False,
        auth_secret_key="test-auth-secret",
    )
    session_id = uuid4()
    context = replace(
        api_context(role=WorkspaceRole.OWNER),
        csrf_token=csrf_token_for_session(session_id, settings),
        session_id=session_id,
    )
    binder = ChatIdentityBinderStub()
    issuer = TelegramLinkCodeIssuerStub()
    app.state.test_actor_id = context.workspace.user.id
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_chat_identity_binder] = lambda: binder
    app.dependency_overrides[get_telegram_link_code_issuer] = lambda: issuer
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.test_csrf_token = context.csrf_token
    app.state.test_link_code_issuer = issuer
    return app, binder


def test_telegram_link_code_requires_csrf_and_is_not_cached() -> None:
    app, _ = chat_integrations_app(environment="production")

    with TestClient(app) as client:
        rejected = client.post("/api/v1/chat-integrations/telegram/link-code")
        response = client.post(
            "/api/v1/chat-integrations/telegram/link-code",
            headers={"X-CSRF-Token": app.state.test_csrf_token},
        )

    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "invalid_csrf"
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "command": "/link workspace-id.secret",
        "expiresAt": "2026-08-29T12:00:00Z",
    }
    assert app.state.test_link_code_issuer.calls == 1


def test_telegram_dev_link_reads_config_and_binds_normalized_identity() -> None:
    app, binder = chat_integrations_app()

    with TestClient(app) as client:
        config = client.get("/api/v1/chat-integrations/telegram/dev-link")
        response = client.post(
            "/api/v1/chat-integrations/telegram/dev-link",
            json={"externalUserId": " 42 ", "displayName": " Max "},
        )

    assert config.status_code == 200
    assert config.json() == {"enabled": True}
    assert response.status_code == 200
    assert response.json() == {"bound": True}
    command = binder.commands[0]
    assert command.external_user_id == "42"
    assert command.display_name == "Max"
    assert command.user_id == app.state.test_actor_id


def test_telegram_dev_link_is_hidden_in_production() -> None:
    app, _ = chat_integrations_app(environment="production")

    with TestClient(app) as client:
        response = client.get("/api/v1/chat-integrations/telegram/dev-link")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_telegram_dev_link_maps_binding_error() -> None:
    app, binder = chat_integrations_app()
    binder.error = ChatIdentityBindingError("This chat identity is already linked.")

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat-integrations/telegram/dev-link",
            json={"externalUserId": "42"},
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "chat_identity_binding_failed",
        "message": "This chat identity is already linked.",
    }
