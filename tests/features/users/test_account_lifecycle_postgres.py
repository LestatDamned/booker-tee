import os
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import hash_password, hash_session_token
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.ledger.models import Operation
from app.features.users.account_deactivation import AccountDeactivationService
from app.features.users.email_change import EmailChangeService
from app.features.users.errors import (
    AccountDeactivationBlockedError,
    EmailAlreadyRegisteredError,
)
from app.features.users.models import User, UserSession
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.repository import WorkspaceRepository

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL lifecycle tests.",
)


async def test_email_change_updates_email_and_rotates_current_session(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    user_id, session_ids, old_email = await seed_email_change_user(sessions)
    new_email = f"new-{uuid4()}@example.test"
    settings = Settings(auth_secret_key="email-change-test-secret-at-least-32-bytes")

    async with sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None
        requested = await EmailChangeService(session, settings).request_change(
            user=user,
            current_password="current secure phrase",
            target_email=new_email.upper(),
            base_url="https://booker.example",
        )
        assert requested.messages[0].recipient == old_email
        assert "token=" not in requested.messages[0].text
        assert requested.messages[1].recipient == new_email
        token = parse_qs(urlparse(requested.messages[1].text.splitlines()[2]).fragment)["token"][0]

    async with sessions() as session:
        user = await session.get(User, user_id)
        user_sessions = list(
            await session.scalars(
                select(UserSession).where(UserSession.user_id == user_id)
            )
        )
        assert user is not None and user.email == old_email
        assert len(user_sessions) == 2
        assert all(user_session.revoked_at is None for user_session in user_sessions)
        result = await EmailChangeService(session, settings).confirm_change(
            user=user,
            session_token=session_ids[0],
            token=token,
        )
        rotated_token = result.tokens.refresh_token
        assert result.notification.recipient == old_email

    async with sessions() as session:
        user = await session.get(User, user_id)
        current = await session.get(UserSession, session_ids[0])
        other = await session.get(UserSession, session_ids[1])
        assert user is not None and user.email == new_email
        assert current is not None
        assert current.session_token_hash == hash_session_token(rotated_token)
        assert other is not None and other.revoked_at is not None


async def test_email_change_rechecks_collision_at_confirmation(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    user_id, session_ids, old_email = await seed_email_change_user(sessions)
    collision_email = f"collision-{uuid4()}@example.test"
    settings = Settings(auth_secret_key="email-change-test-secret-at-least-32-bytes")

    async with sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None
        requested = await EmailChangeService(session, settings).request_change(
            user=user,
            current_password="current secure phrase",
            target_email=collision_email,
            base_url="https://booker.example",
        )
        collision_token = parse_qs(urlparse(requested.messages[1].text.splitlines()[2]).fragment)[
            "token"
        ][0]

    async with sessions() as session:
        session.add(
            User(
                id=uuid4(),
                email=collision_email,
                password_hash="hash",
                email_verified_at=utc_now(),
            )
        )
        await session.commit()

    async with sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None
        with pytest.raises(EmailAlreadyRegisteredError):
            await EmailChangeService(session, settings).confirm_change(
                user=user,
                session_token=session_ids[0],
                token=collision_token,
            )

    async with sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None and user.email == old_email


async def seed_email_change_user(
    sessions: async_sessionmaker[Any],
) -> tuple[UUID, list[UUID], str]:
    unique = uuid4()
    user_id = uuid4()
    session_ids = [uuid4(), uuid4()]
    old_email = f"old-{unique}@example.test"
    async with sessions() as session:
        session.add(
            User(
                id=user_id,
                email=old_email,
                password_hash=hash_password("current secure phrase"),
                email_verified_at=utc_now(),
            )
        )
        session.add_all(
            [
                UserSession(
                    id=session_ids[0],
                    user_id=user_id,
                    session_token_hash=hash_session_token(f"current-{unique}"),
                    expires_at=utc_now() + timedelta(days=1),
                ),
                UserSession(
                    id=session_ids[1],
                    user_id=user_id,
                    session_token_hash="f" * 64,
                    expires_at=utc_now() + timedelta(days=1),
                ),
            ]
        )
        await session.commit()
    return user_id, session_ids, old_email


async def test_deactivation_blocks_shared_ownership_then_preserves_financial_history(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    owner_id = uuid4()
    member_id = uuid4()
    session_id = uuid4()
    operation_id = uuid4()

    async with sessions() as session:
        session.add_all(
            [
                User(
                    id=owner_id,
                    email=f"owner-{owner_id}@example.test",
                    password_hash=hash_password("current secure phrase"),
                    email_verified_at=utc_now(),
                ),
                User(
                    id=member_id,
                    email=f"member-{member_id}@example.test",
                    password_hash="hash",
                    email_verified_at=utc_now(),
                ),
            ]
        )
        await session.flush()
        workspaces = WorkspaceRepository(session)
        sole, _ = await workspaces.create_workspace_with_owner_membership(
            owner_id=owner_id,
            name="Личное",
            workspace_type=WorkspaceType.PERSONAL,
            default_currency="RUB",
        )
        shared, _ = await workspaces.create_workspace_with_owner_membership(
            owner_id=owner_id,
            name="Семья",
            workspace_type=WorkspaceType.FAMILY,
            default_currency="RUB",
        )
        await workspaces.create_member(
            workspace_id=shared.id,
            user_id=member_id,
            role=WorkspaceRole.VIEWER,
        )
        workspace_ids = [sole.id, shared.id]
        session.add(
            UserSession(
                id=session_id,
                user_id=owner_id,
                session_token_hash="e" * 64,
                current_workspace_id=sole.id,
                expires_at=utc_now() + timedelta(days=1),
            )
        )
        session.add(
            Operation(
                id=operation_id,
                workspace_id=sole.id,
                type=OperationType.EXPENSE,
                status=OperationStatus.CONFIRMED,
                affects_profit=True,
                description="Preserved record",
                operation_date=date.today(),
                created_by_user_id=owner_id,
            )
        )
        await session.commit()

    async with sessions() as session:
        owner = await session.get(User, owner_id)
        assert owner is not None
        impact = await AccountDeactivationService(session).impact(user_id=owner_id)
        assert not impact.can_deactivate
        assert [item.workspace_name for item in impact.blockers] == ["Семья"]
        with pytest.raises(AccountDeactivationBlockedError):
            await AccountDeactivationService(session).deactivate(
                user=owner,
                current_password="current secure phrase",
            )

    async with sessions() as session:
        membership = await session.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_ids[1],
                WorkspaceMember.user_id == member_id,
            )
        )
        assert membership is not None
        membership.status = WorkspaceMemberStatus.DISABLED
        await session.commit()

    async with sessions() as session:
        owner = await session.get(User, owner_id)
        assert owner is not None
        await AccountDeactivationService(session).deactivate(
            user=owner,
            current_password="current secure phrase",
        )

    async with sessions() as session:
        owner = await session.get(User, owner_id)
        workspace_states = list(
            await session.scalars(
                select(Workspace.is_active)
                .where(Workspace.id.in_(workspace_ids))
                .order_by(Workspace.id)
            )
        )
        active_session = await session.scalar(
            select(UserSession.id).where(
                UserSession.id == session_id,
                UserSession.revoked_at.is_(None),
            )
        )
        assert owner is not None and not owner.is_active and owner.deactivated_at is not None
        assert workspace_states == [False, False]
        assert active_session is None
        assert await session.get(Operation, operation_id) is not None
