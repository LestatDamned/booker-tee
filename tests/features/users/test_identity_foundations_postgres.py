import asyncio
import os
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import (
    auth_rate_limit_bucket_hash,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.email_verification import EmailVerificationService
from app.features.users.errors import (
    AuthRateLimitedError,
    InvalidCredentialsError,
    InvalidEmailVerificationTokenError,
    InvalidPasswordResetTokenError,
    UserSessionNotFoundError,
)
from app.features.users.identity_repository import (
    AuthRateLimitRepository,
    UserTokenRepository,
)
from app.features.users.models import (
    AuthRateLimit,
    User,
    UserSession,
    UserToken,
    UserTokenPurpose,
)
from app.features.users.passwords import PasswordService
from app.features.users.service import AuthenticationService
from app.features.users.sessions import UserSessionService
from app.features.workspaces.domain.types import (
    WorkspaceInvitationStatus,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEvent,
    WorkspaceInvitation,
    WorkspaceMember,
)
from app.features.workspaces.tokens import hash_invitation_token

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL identity tests.",
)


async def test_token_replacement_and_consumption_are_concurrency_safe(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    user_id = uuid4()

    async with sessions() as session:
        session.add(
            User(
                id=user_id,
                email=f"identity-{user_id}@example.test",
                password_hash="hash",
                name="Identity foundations",
            )
        )
        await session.commit()

    try:
        async with sessions() as session:
            tokens = UserTokenRepository(session)
            first = await tokens.replace_active(
                user_id=user_id,
                purpose=UserTokenPurpose.VERIFY_EMAIL,
                token_hash="1" * 64,
                expires_at=utc_now() + timedelta(hours=1),
            )
            await session.commit()
            first_id = first.id

        async with sessions() as session:
            tokens = UserTokenRepository(session)
            second = await tokens.replace_active(
                user_id=user_id,
                purpose=UserTokenPurpose.VERIFY_EMAIL,
                token_hash="2" * 64,
                expires_at=utc_now() + timedelta(hours=1),
            )
            await session.commit()
            second_id = second.id

        async with sessions() as session:
            first = await session.get(UserToken, first_id)
            assert first is not None and first.consumed_at is not None

        async def consume() -> bool:
            async with sessions() as session:
                token = await UserTokenRepository(session).consume(
                    purpose=UserTokenPurpose.VERIFY_EMAIL,
                    token_hash="2" * 64,
                )
                await session.commit()
                return token is not None

        assert sorted(await asyncio.gather(consume(), consume())) == [False, True]

        async with sessions() as session:
            second = await session.get(UserToken, second_id)
            assert second is not None and second.consumed_at is not None
    finally:
        async with sessions() as session:
            await session.execute(delete(UserToken).where(UserToken.user_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_rate_limit_increment_is_concurrency_safe(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    bucket_hash = uuid4().hex * 2

    try:

        async def increment() -> int:
            async with sessions() as session:
                count = await AuthRateLimitRepository(session).increment(
                    bucket_hash=bucket_hash,
                    window=timedelta(minutes=5),
                )
                await session.commit()
                return count

        assert sorted(await asyncio.gather(*(increment() for _ in range(10)))) == list(range(1, 11))
        async with sessions() as session:
            assert (
                await session.scalar(
                    select(AuthRateLimit.attempt_count).where(
                        AuthRateLimit.bucket_hash == bucket_hash
                    )
                )
                == 10
            )
    finally:
        async with sessions() as session:
            await session.execute(
                delete(AuthRateLimit).where(AuthRateLimit.bucket_hash == bucket_hash)
            )
            await session.commit()


async def test_session_directory_is_user_scoped(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    user_ids, session_ids = await seed_user_sessions(sessions)
    settings = Settings(auth_secret_key="session-management-test-secret")

    async with sessions() as session:
        snapshots = await UserSessionService(session, settings).list_active(
            user_id=user_ids[0],
            current_session_id=session_ids[0],
        )

    assert [snapshot.id for snapshot in snapshots] == session_ids[:2]
    assert [snapshot.is_current for snapshot in snapshots] == [True, False]


async def test_session_revoke_masks_foreign_session(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    user_ids, session_ids = await seed_user_sessions(sessions)
    settings = Settings(auth_secret_key="session-management-test-secret")

    async with sessions() as session:
        with pytest.raises(UserSessionNotFoundError):
            await UserSessionService(session, settings).revoke(
                user_id=user_ids[0],
                current_session_id=session_ids[0],
                session_id=session_ids[2],
            )

    async with sessions() as session:
        foreign_session = await session.get(UserSession, session_ids[2])
        assert foreign_session is not None and foreign_session.revoked_at is None


async def test_revoke_other_sessions_preserves_current_and_foreign(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    user_ids, session_ids = await seed_user_sessions(sessions)
    settings = Settings(auth_secret_key="session-management-test-secret")

    async with sessions() as session:
        revoked_count = await UserSessionService(session, settings).revoke_others(
            user_id=user_ids[0],
            current_session_id=session_ids[0],
        )

    assert revoked_count == 1

    async with sessions() as session:
        current = await session.get(UserSession, session_ids[0])
        other = await session.get(UserSession, session_ids[1])
        foreign = await session.get(UserSession, session_ids[2])
        assert current is not None and current.revoked_at is None
        assert other is not None and other.revoked_at is not None
        assert foreign is not None and foreign.revoked_at is None


async def seed_user_sessions(
    sessions: async_sessionmaker[Any],
) -> tuple[list[UUID], list[UUID]]:
    user_ids = [uuid4(), uuid4()]
    session_ids = [uuid4(), uuid4(), uuid4()]
    now = utc_now()
    async with sessions() as session:
        session.add_all(
            User(
                id=user_id,
                email=f"sessions-{user_id}@example.test",
                password_hash="hash",
                email_verified_at=now,
            )
            for user_id in user_ids
        )
        session.add_all(
            UserSession(
                id=session_id,
                user_id=user_ids[0] if index < 2 else user_ids[1],
                session_token_hash=hash_session_token(f"session-{session_id}"),
                last_seen_at=now - timedelta(minutes=index) if index < 2 else now,
                expires_at=now + timedelta(days=1),
                user_agent_summary=("Chrome · Linux", "Safari · iPhone", None)[index],
            )
            for index, session_id in enumerate(session_ids)
        )
        await session.commit()
    return user_ids, session_ids


async def test_verification_first_signup_creates_identity_then_workspace_once(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    identity_id = uuid4()
    email = f"verification-{identity_id}@example.test"
    settings = Settings(
        auth_secret_key="verification-first-signup-test-secret",
        public_base_url="https://booker.example",
    )
    user_id = None
    workspace_id = None

    try:

        async def signup():
            async with sessions() as session:
                return await EmailVerificationService(session, settings).request_signup(
                    email=email,
                    password="correct horse battery staple",
                    name="First name",
                    base_url="https://booker.example",
                    next_path="/workspaces/invitations/example",
                )

        signup_results = await asyncio.gather(signup(), signup())
        messages = [result.email for result in signup_results if result.email is not None]
        assert len(messages) == 1
        token = parse_qs(urlparse(messages[0].text.splitlines()[2]).fragment)["token"][0]

        async with sessions() as session:
            user = await session.scalar(select(User).where(User.email == email))
            assert user is not None
            user_id = user.id
            assert user.email_verified_at is None
            assert (
                await session.scalar(select(Workspace.id).where(Workspace.owner_id == user.id))
                is None
            )
            assert (
                await session.scalar(select(UserSession.id).where(UserSession.user_id == user.id))
                is None
            )
            with pytest.raises(InvalidCredentialsError):
                await AuthenticationService(session, settings).login(
                    email=email,
                    password="correct horse battery staple",
                )

        async with sessions() as session:
            repeated = await EmailVerificationService(session, settings).request_signup(
                email=email,
                password="a different password that must not replace credentials",
                name="Changed name",
                base_url="https://booker.example",
            )
            assert repeated.email is None

        async def verify() -> bool:
            async with sessions() as session:
                try:
                    await EmailVerificationService(session, settings).verify(token=token)
                except InvalidEmailVerificationTokenError:
                    return False
                return True

        assert sorted(await asyncio.gather(verify(), verify())) == [False, True]

        async with sessions() as session:
            assert user_id is not None
            user = await session.get(User, user_id)
            assert user is not None
            assert user.email_verified_at is not None
            assert user.name == "First name"
            assert verify_password("correct horse battery staple", user.password_hash)
            assert not verify_password(
                "a different password that must not replace credentials",
                user.password_hash,
            )
            workspace_ids = list(
                (
                    await session.scalars(select(Workspace.id).where(Workspace.owner_id == user.id))
                ).all()
            )
            assert len(workspace_ids) == 1
            workspace_id = workspace_ids[0]
            assert (
                await session.scalar(select(UserSession.id).where(UserSession.user_id == user.id))
                is not None
            )
    finally:
        async with sessions() as session:
            rate_limit_hashes = [
                auth_rate_limit_bucket_hash(scope=scope, key=key, settings=settings)
                for scope, key in (
                    ("signup-account", email),
                    ("signup-network", "unknown"),
                    ("login-account", email),
                    ("login-network", "unknown"),
                )
            ]
            await session.execute(
                delete(AuthRateLimit).where(AuthRateLimit.bucket_hash.in_(rate_limit_hashes))
            )
            if user_id is not None:
                await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
                await session.execute(delete(UserToken).where(UserToken.user_id == user_id))
            if workspace_id is not None:
                await session.execute(
                    delete(WorkspaceAuditEvent).where(
                        WorkspaceAuditEvent.workspace_id == workspace_id
                    )
                )
                await session.execute(
                    delete(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
                )
                await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            if user_id is not None:
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_invite_only_signup_uses_pending_workspace_invitation(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    owner_id = uuid4()
    workspace_id = uuid4()
    invitation_id = uuid4()
    token = f"signup-invitation-{invitation_id}"
    email = f"invited-{invitation_id}@example.test"
    settings = Settings(
        auth_secret_key="invite-only-signup-test-secret",
        registration_mode="invite_only",
    )

    async with sessions() as session:
        session.add(
            User(
                id=owner_id,
                email=f"owner-{owner_id}@example.test",
                password_hash="hash",
                name="Owner",
                email_verified_at=utc_now(),
            )
        )
        session.add(
            Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Invited workspace",
            )
        )
        session.add(
            WorkspaceMember(
                workspace_id=workspace_id,
                user_id=owner_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            )
        )
        session.add(
            WorkspaceInvitation(
                id=invitation_id,
                workspace_id=workspace_id,
                invitee_email=email,
                role=WorkspaceRole.VIEWER,
                status=WorkspaceInvitationStatus.PENDING,
                token_hash=hash_invitation_token(token),
                invited_by_user_id=owner_id,
                expires_at=utc_now() + timedelta(hours=1),
            )
        )
        await session.commit()

    async with sessions() as session:
        result = await EmailVerificationService(session, settings).request_signup(
            email=email,
            password="correct horse battery staple",
            name="Invitee",
            base_url="https://booker.example",
            invitation_token=token,
        )
        assert result.email is not None
        assert await session.scalar(select(User.id).where(User.email == email)) is not None
        invitation = await session.get(WorkspaceInvitation, invitation_id)
        assert invitation is not None
        assert invitation.status == WorkspaceInvitationStatus.PENDING


async def test_verification_resend_is_generic_and_rate_limited_for_known_and_unknown(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    unique = uuid4()
    email = f"unknown-{unique}@example.test"
    network_key = f"network-{unique}"
    settings = Settings(auth_secret_key="verification-resend-test-secret")
    async with sessions() as session:
        result = await EmailVerificationService(session, settings).request_resend(
            email=email,
            base_url="https://booker.example",
            network_key=network_key,
        )
        assert result.email is None

    async with sessions() as session:
        with pytest.raises(AuthRateLimitedError):
            await EmailVerificationService(session, settings).request_resend(
                email=email,
                base_url="https://booker.example",
                network_key=network_key,
            )


async def test_password_change_rotates_current_session_and_revokes_others(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    user_id, session_ids, _email, current_token = await seed_password_user(sessions)
    settings = Settings(
        auth_secret_key="password-lifecycle-test-secret-32-bytes",
        public_base_url="https://booker.example",
    )

    async with sessions() as session:
        user = await session.get(User, user_id)
        assert user is not None
        rotated_token = await PasswordService(session, settings).change_password(
            user=user,
            session_token=session_ids[0],
            current_password="old secure phrase",
            new_password="new secure phrase",
        )
        assert rotated_token.refresh_token != current_token

    async with sessions() as session:
        current = await session.get(UserSession, session_ids[0])
        other = await session.get(UserSession, session_ids[1])
        user = await session.get(User, user_id)
        assert current is not None and current.revoked_at is None
        assert current.session_token_hash == hash_session_token(rotated_token.refresh_token)
        assert other is not None and other.revoked_at is not None
        assert user is not None and verify_password("new secure phrase", user.password_hash)


async def test_password_reset_changes_password_revokes_sessions_and_consumes_token(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    user_id, _session_ids, email, _current_token = await seed_password_user(sessions)
    network_key = f"network-{uuid4()}"
    settings = Settings(
        auth_secret_key="password-lifecycle-test-secret-32-bytes",
        public_base_url="https://booker.example",
    )

    async with sessions() as session:
        request = await PasswordService(session, settings).request_reset(
            email=email,
            base_url="https://booker.example",
            network_key=network_key,
        )
        assert request.email is not None
        reset_token = parse_qs(urlparse(request.email.text.splitlines()[2]).fragment)["token"][0]

    async with sessions() as session:
        await PasswordService(session, settings).reset_password(
            token=reset_token,
            new_password="final secure phrase",
            network_key=network_key,
        )

    async with sessions() as session:
        user = await session.get(User, user_id)
        active_session = await session.scalar(
            select(UserSession.id).where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
        )
        assert user is not None
        assert verify_password("final secure phrase", user.password_hash)
        assert active_session is None
        with pytest.raises(InvalidPasswordResetTokenError):
            await PasswordService(session, settings).reset_password(
                token=reset_token,
                new_password="another secure phrase",
                network_key=network_key,
            )


async def seed_password_user(
    sessions: async_sessionmaker[Any],
) -> tuple[UUID, list[UUID], str, str]:
    unique = uuid4()
    user_id = uuid4()
    session_ids = [uuid4(), uuid4()]
    email = f"password-{unique}@example.test"
    current_token = f"current-{unique}"
    async with sessions() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                password_hash=hash_password("old secure phrase"),
                email_verified_at=utc_now(),
            )
        )
        session.add_all(
            [
                UserSession(
                    id=session_ids[0],
                    user_id=user_id,
                    session_token_hash=hash_session_token(current_token),
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
    return user_id, session_ids, email, current_token
