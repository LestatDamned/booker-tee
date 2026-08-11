from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.chat_integrations.actions.identity import BindChatIdentityCommand
from app.features.chat_integrations.errors import (
    ChatIdentityBindingError,
    ChatWorkspaceResolutionError,
)
from app.features.chat_integrations.schemas import (
    ChatProviderCode,
    ChatUser,
    InboundChatEvent,
    InboundChatEventType,
)
from app.features.chat_integrations.use_cases import identity as chat_identity
from app.features.chat_integrations.use_cases import workspace as chat_workspace


@pytest.mark.asyncio
async def test_chat_identity_binder_rejects_user_without_workspace_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSession:
        async def commit(self) -> None:
            raise AssertionError("commit must not be called")

    class FakeChatIntegrationRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def lock_for_update(self, workspace_id):
            return SimpleNamespace(id=workspace_id, is_active=True)

        async def get_active_membership(self, **_kwargs):
            return None

    monkeypatch.setattr(chat_identity, "ChatIntegrationRepository", FakeChatIntegrationRepository)
    monkeypatch.setattr(chat_identity, "WorkspaceRepository", FakeWorkspaceRepository)

    binder = chat_identity.ChatIdentityBinder(cast(AsyncSession, FakeSession()))

    with pytest.raises(ChatIdentityBindingError):
        await binder.bind_chat_identity(
            BindChatIdentityCommand(
                workspace_id=uuid4(),
                user_id=uuid4(),
                provider=ChatProviderCode.TELEGRAM,
                external_user_id="42",
                display_name="Anna",
            )
        )


@pytest.mark.asyncio
async def test_chat_identity_binder_creates_binding_for_active_workspace_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    workspace_id = uuid4()

    class FakeSession:
        def __init__(self) -> None:
            self.commit_count = 0
            self.created_binding = None

        async def commit(self) -> None:
            self.commit_count += 1

    class FakeChatIntegrationRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def get_active_identity_binding(self, **_kwargs):
            return None

        async def create_identity_binding(self, **values):
            binding = SimpleNamespace(id=uuid4(), **values)
            self.session.created_binding = binding
            return binding

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def lock_for_update(self, requested_workspace_id):
            return SimpleNamespace(id=requested_workspace_id, is_active=True)

        async def get_active_membership(self, **_kwargs):
            return SimpleNamespace(id=uuid4(), workspace_id=workspace_id, user_id=user_id)

    monkeypatch.setattr(chat_identity, "ChatIntegrationRepository", FakeChatIntegrationRepository)
    monkeypatch.setattr(chat_identity, "WorkspaceRepository", FakeWorkspaceRepository)

    session = FakeSession()
    binder = chat_identity.ChatIdentityBinder(cast(AsyncSession, session))

    binding = await binder.bind_chat_identity(
        BindChatIdentityCommand(
            workspace_id=workspace_id,
            user_id=user_id,
            provider=ChatProviderCode.TELEGRAM,
            external_user_id="42",
            display_name="Anna",
        )
    )

    assert session.commit_count == 1
    assert binding.workspace_id == workspace_id
    assert binding.user_id == user_id
    assert binding.provider == ChatProviderCode.TELEGRAM
    assert binding.external_user_id == "42"


@pytest.mark.asyncio
async def test_workspace_chat_resolver_rejects_unbound_chat_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChatIntegrationRepository:
        def __init__(self, _session) -> None:
            pass

        async def list_active_identity_bindings_for_external_user(self, **_kwargs):
            return []

    monkeypatch.setattr(chat_workspace, "ChatIntegrationRepository", FakeChatIntegrationRepository)

    resolver = chat_workspace.WorkspaceChatResolver(cast(AsyncSession, object()))
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=None,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        text="/start",
    )

    with pytest.raises(ChatWorkspaceResolutionError):
        await resolver.require_bound_workspace(event)


@pytest.mark.asyncio
async def test_workspace_chat_resolver_rechecks_membership_for_existing_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    binding = SimpleNamespace(user_id=user_id, workspace_id=workspace_id)

    class FakeChatIntegrationRepository:
        def __init__(self, _session) -> None:
            pass

        async def list_active_identity_bindings_for_external_user(self, **_kwargs):
            return [binding]

    class FakeUserRepository:
        def __init__(self, _session) -> None:
            pass

        async def get_active(self, requested_user_id):
            assert requested_user_id == user_id
            return SimpleNamespace(id=user_id, is_active=True)

    class FakeWorkspaceRepository:
        def __init__(self, _session) -> None:
            pass

        async def lock_for_update(self, requested_workspace_id):
            assert requested_workspace_id == workspace_id
            return SimpleNamespace(id=workspace_id, is_active=True)

        async def get_active_membership(self, **kwargs):
            assert kwargs == {"user_id": user_id, "workspace_id": workspace_id}
            return None

    monkeypatch.setattr(chat_workspace, "ChatIntegrationRepository", FakeChatIntegrationRepository)
    monkeypatch.setattr(chat_workspace, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(chat_workspace, "WorkspaceRepository", FakeWorkspaceRepository)

    resolver = chat_workspace.WorkspaceChatResolver(cast(AsyncSession, object()))
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.CALLBACK_QUERY,
        conversation=None,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        callback_data="menu",
    )

    with pytest.raises(ChatWorkspaceResolutionError):
        await resolver.require_bound_workspace(event)


@pytest.mark.asyncio
async def test_workspace_chat_resolver_returns_workspace_context_for_bound_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    workspace = SimpleNamespace(id=workspace_id, name="Personal")
    membership = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        workspace_id=workspace_id,
        workspace=workspace,
    )
    user = SimpleNamespace(id=user_id, is_active=True)
    binding = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        workspace_id=workspace_id,
        provider=ChatProviderCode.TELEGRAM,
        external_user_id="42",
    )

    class FakeChatIntegrationRepository:
        def __init__(self, _session) -> None:
            pass

        async def list_active_identity_bindings_for_external_user(self, **_kwargs):
            return [binding]

    class FakeUserRepository:
        def __init__(self, _session) -> None:
            pass

        async def get_active(self, requested_user_id):
            assert requested_user_id == user_id
            return user

    class FakeWorkspaceRepository:
        def __init__(self, _session) -> None:
            pass

        async def lock_for_update(self, requested_workspace_id):
            assert requested_workspace_id == workspace_id
            return SimpleNamespace(id=workspace_id, is_active=True)

        async def get_active_membership(self, **kwargs):
            assert kwargs == {"user_id": user_id, "workspace_id": workspace_id}
            return membership

    monkeypatch.setattr(chat_workspace, "ChatIntegrationRepository", FakeChatIntegrationRepository)
    monkeypatch.setattr(chat_workspace, "UserRepository", FakeUserRepository)
    monkeypatch.setattr(chat_workspace, "WorkspaceRepository", FakeWorkspaceRepository)

    resolver = chat_workspace.WorkspaceChatResolver(cast(AsyncSession, object()))
    event = InboundChatEvent(
        provider=ChatProviderCode.TELEGRAM,
        event_id="1",
        event_type=InboundChatEventType.MESSAGE,
        conversation=None,
        actor=ChatUser(provider=ChatProviderCode.TELEGRAM, external_user_id="42"),
        text="/start",
    )

    bound_workspace = await resolver.require_bound_workspace(event)

    assert bound_workspace.identity_binding is binding
    assert bound_workspace.context.user is user
    assert bound_workspace.context.workspace is workspace
    assert bound_workspace.context.membership is membership
