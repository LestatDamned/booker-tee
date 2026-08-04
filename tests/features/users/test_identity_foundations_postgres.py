import asyncio
import os
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import (
    auth_rate_limit_bucket_hash,
    hash_password,
    hash_session_token,
    hash_user_token,
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
from app.features.workspaces.models import Workspace, WorkspaceAuditEvent, WorkspaceMember

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL identity tests.",
)


@pytest.mark.asyncio
async def test_token_replacement_consumption_and_rate_limit_are_concurrency_safe() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    bucket_hash = "a" * 64

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
            assert await session.get(UserToken, second_id) is not None
    finally:
        async with sessions() as session:
            await session.execute(
                delete(AuthRateLimit).where(AuthRateLimit.bucket_hash == bucket_hash)
            )
            await session.execute(delete(UserToken).where(UserToken.user_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_verification_first_signup_creates_identity_then_workspace_once() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
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
        token = parse_qs(urlparse(messages[0].text.splitlines()[2]).query)["token"][0]

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
        await engine.dispose()


@pytest.mark.asyncio
async def test_verification_resend_is_generic_and_rate_limited_for_known_and_unknown() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4()
    email = f"unknown-{unique}@example.test"
    network_key = f"network-{unique}"
    settings = Settings(auth_secret_key="verification-resend-test-secret")
    bucket_hashes = [
        auth_rate_limit_bucket_hash(
            scope=scope,
            key=key,
            settings=settings,
        )
        for scope, key in (
            ("verification-resend-account", email),
            ("verification-resend-network", network_key),
        )
    ]

    try:
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
    finally:
        async with sessions() as session:
            await session.execute(
                delete(AuthRateLimit).where(AuthRateLimit.bucket_hash.in_(bucket_hashes))
            )
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_password_change_rotates_current_session_and_reset_revokes_every_session() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    unique = uuid4()
    email = f"password-{unique}@example.test"
    current_token = f"current-{unique}"
    settings = Settings(
        auth_secret_key="password-lifecycle-test-secret",
        public_base_url="https://booker.example",
    )
    user_id = uuid4()
    session_ids = [uuid4(), uuid4()]
    reset_token: str | None = None

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

    try:
        async with sessions() as session:
            user = await session.get(User, user_id)
            assert user is not None
            rotated_token = await PasswordService(session, settings).change_password(
                user=user,
                session_token=current_token,
                current_password="old secure phrase",
                new_password="new secure phrase",
            )
            assert rotated_token != current_token

        async with sessions() as session:
            current = await session.get(UserSession, session_ids[0])
            other = await session.get(UserSession, session_ids[1])
            user = await session.get(User, user_id)
            assert current is not None and current.revoked_at is None
            assert current.session_token_hash == hash_session_token(rotated_token)
            assert other is not None and other.revoked_at is not None
            assert user is not None and verify_password("new secure phrase", user.password_hash)

            request = await PasswordService(session, settings).request_reset(
                email=email,
                base_url="https://booker.example",
                network_key=f"network-{unique}",
            )
            assert request.email is not None
            reset_token = parse_qs(urlparse(request.email.text.splitlines()[2]).query)["token"][0]

        async with sessions() as session:
            await PasswordService(session, settings).reset_password(
                token=reset_token,
                new_password="final secure phrase",
                network_key=f"network-{unique}",
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
                    network_key=f"network-{unique}",
                )
    finally:
        async with sessions() as session:
            rate_limit_hashes = [
                auth_rate_limit_bucket_hash(scope=scope, key=key, settings=settings)
                for scope, key in (
                    ("password-reset-account", email),
                    ("password-reset-network", f"network-{unique}"),
                    ("password-reset-attempt-network", f"network-{unique}"),
                )
            ]
            if reset_token is not None:
                rate_limit_hashes.append(
                    auth_rate_limit_bucket_hash(
                        scope="password-reset-token",
                        key=hash_user_token(reset_token),
                        settings=settings,
                    )
                )
            await session.execute(
                delete(AuthRateLimit).where(AuthRateLimit.bucket_hash.in_(rate_limit_hashes))
            )
            await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
            await session.execute(delete(UserToken).where(UserToken.user_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
