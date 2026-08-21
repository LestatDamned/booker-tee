from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock, create_autospec
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.core.settings import Settings
from app.features.users import bootstrap as bootstrap_module
from app.features.users.bootstrap import OwnerBootstrapService
from app.features.users.errors import BootstrapOwnerError
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.features.workspaces.domain.types import WorkspaceType
from app.features.workspaces.repository import WorkspaceRepository


async def test_owner_bootstrap_creates_verified_owner_workspace_atomically() -> None:
    user = cast(User, SimpleNamespace(id=uuid4(), email_verified_at=None))
    workspace = SimpleNamespace(
        id=uuid4(),
        name="Personal",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )
    users = create_autospec(UserRepository, instance=True)
    users.has_any.return_value = False
    users.create.return_value = user
    create_user = users.create
    workspaces = create_autospec(WorkspaceRepository, instance=True)
    workspaces.create_personal_workspace_with_owner_membership.return_value = (
        workspace,
        SimpleNamespace(),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = OwnerBootstrapService(cast(AsyncSession, session), Settings())
    service.users = users
    service.workspaces = workspaces

    result = await service.create_first_owner(
        email=" OWNER@Example.Test ",
        name=" Owner ",
        password="correct horse battery staple",
    )

    assert result is user
    assert user.email_verified_at is not None
    assert create_user.await_args is not None
    create_arguments = create_user.await_args.kwargs
    assert create_arguments["email"] == "owner@example.test"
    assert create_arguments["name"] == "Owner"
    assert verify_password("correct horse battery staple", create_arguments["password_hash"])
    users.lock_for_owner_bootstrap.assert_awaited_once_with()
    workspaces.create_personal_workspace_with_owner_membership.assert_awaited_once_with(user.id)
    workspaces.create_audit_event.assert_awaited_once()
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


async def test_owner_bootstrap_rejects_existing_installation() -> None:
    users = create_autospec(UserRepository, instance=True)
    users.has_any.return_value = True
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = OwnerBootstrapService(cast(AsyncSession, session), Settings())
    service.users = users

    with pytest.raises(BootstrapOwnerError, match="already been completed"):
        await service.create_first_owner(
            email="owner@example.test",
            name="Owner",
            password="correct horse battery staple",
        )

    users.create.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()


def test_owner_bootstrap_does_not_print_mismatched_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter(("owner@example.test", "Owner"))
    password_prompt = Mock(side_effect=("secret-one", "secret-two"))
    monkeypatch.setattr(bootstrap_module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    monkeypatch.setattr(bootstrap_module, "getpass", password_prompt)

    with pytest.raises(SystemExit):
        bootstrap_module.main()

    output = capsys.readouterr()
    assert "Passwords do not match" in output.err
    assert "secret-one" not in output.err
    assert "secret-two" not in output.err


def test_owner_bootstrap_rejects_non_interactive_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    password_prompt = Mock()
    monkeypatch.setattr(bootstrap_module.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(bootstrap_module, "getpass", password_prompt)

    with pytest.raises(SystemExit):
        bootstrap_module.main()

    assert "requires an interactive terminal" in capsys.readouterr().err
    password_prompt.assert_not_called()
