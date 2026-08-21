import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.security import hash_session_token
from app.db.base import utc_now
from app.features.users.models import User, UserSession
from app.features.workspaces.application.ownership import WorkspaceOwnershipService
from app.features.workspaces.commands import TransferWorkspaceOwnershipCommand
from app.features.workspaces.domain.types import WorkspaceMemberStatus, WorkspaceRole, WorkspaceType
from app.features.workspaces.errors import WorkspaceOwnershipTransferConflictError
from app.features.workspaces.models import Workspace, WorkspaceAuditEvent, WorkspaceMember

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for ownership concurrency tests.",
)


async def test_concurrent_transfer_preserves_exactly_one_authoritative_owner(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    seed = await seed_transfer_race(sessions)

    async def transfer(recipient_member_id: UUID, recipient_updated_at: datetime):
        async with sessions() as session:
            actor = await session.get(User, seed.owner_user_id)
            assert actor is not None
            return await WorkspaceOwnershipService(session).transfer(
                actor=actor,
                session_token=seed.session_token,
                workspace_id=seed.workspace_id,
                command=TransferWorkspaceOwnershipCommand(
                    recipient_member_id=recipient_member_id,
                    expected_workspace_updated_at=seed.workspace_updated_at,
                    expected_recipient_updated_at=recipient_updated_at,
                ),
            )

    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                *(
                    transfer(member_id, member_updated_at)
                    for member_id, member_updated_at in zip(
                        seed.recipient_member_ids,
                        seed.member_updated_ats,
                        strict=True,
                    )
                ),
                return_exceptions=True,
            ),
            timeout=10,
        )
        assert sum(not isinstance(result, BaseException) for result in results) == 1
        assert (
            sum(isinstance(result, WorkspaceOwnershipTransferConflictError) for result in results)
            == 1
        )

        async with sessions() as session:
            workspace = await session.get(Workspace, seed.workspace_id)
            assert workspace is not None
            owner_members = list(
                (
                    await session.scalars(
                        select(WorkspaceMember).where(
                            WorkspaceMember.workspace_id == seed.workspace_id,
                            WorkspaceMember.role == WorkspaceRole.OWNER,
                            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                        )
                    )
                ).all()
            )
            transfer_audits = await session.scalar(
                select(func.count())
                .select_from(WorkspaceAuditEvent)
                .where(
                    WorkspaceAuditEvent.workspace_id == seed.workspace_id,
                    WorkspaceAuditEvent.details["action"].as_string() == "ownership_transferred",
                )
            )

        assert len(owner_members) == 1
        assert owner_members[0].user_id == workspace.owner_id
        assert transfer_audits == 1
    finally:
        await cleanup(sessions, seed)


@dataclass(frozen=True)
class TransferRaceSeed:
    owner_user_id: UUID
    workspace_id: UUID
    recipient_member_ids: tuple[UUID, UUID]
    user_ids: tuple[UUID, UUID, UUID]
    session_token: str
    workspace_updated_at: datetime
    member_updated_ats: tuple[datetime, datetime]


async def seed_transfer_race(sessions: async_sessionmaker[Any]) -> TransferRaceSeed:
    owner_user_id, first_user_id, second_user_id = uuid4(), uuid4(), uuid4()
    workspace_id = uuid4()
    recipient_member_ids = (uuid4(), uuid4())
    session_token = f"workspace-owner-transfer-{uuid4()}"
    now = utc_now()
    users = [
        User(
            id=user_id,
            email=f"ownership-race-{user_id}@example.test",
            password_hash="hash",
            name=name,
        )
        for user_id, name in (
            (owner_user_id, "Owner"),
            (first_user_id, "First recipient"),
            (second_user_id, "Second recipient"),
        )
    ]
    workspace = Workspace(
        id=workspace_id,
        owner_id=owner_user_id,
        name="Ownership race",
        type=WorkspaceType.FAMILY,
        default_currency="RUB",
    )
    members = [
        WorkspaceMember(
            workspace_id=workspace_id,
            user_id=owner_user_id,
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
        WorkspaceMember(
            id=recipient_member_ids[0],
            workspace_id=workspace_id,
            user_id=first_user_id,
            role=WorkspaceRole.EDITOR,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
        WorkspaceMember(
            id=recipient_member_ids[1],
            workspace_id=workspace_id,
            user_id=second_user_id,
            role=WorkspaceRole.ADMIN,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
    ]
    async with sessions() as session:
        session.add_all([*users, workspace, *members])
        session.add(
            UserSession(
                user_id=owner_user_id,
                current_workspace_id=workspace_id,
                session_token_hash=hash_session_token(session_token),
                expires_at=now + timedelta(hours=1),
            )
        )
        await session.commit()
        await session.refresh(workspace)
        await session.refresh(members[1])
        await session.refresh(members[2])

    return TransferRaceSeed(
        owner_user_id=owner_user_id,
        workspace_id=workspace_id,
        recipient_member_ids=recipient_member_ids,
        user_ids=(owner_user_id, first_user_id, second_user_id),
        session_token=session_token,
        workspace_updated_at=workspace.updated_at,
        member_updated_ats=(members[1].updated_at, members[2].updated_at),
    )


async def cleanup(sessions: async_sessionmaker[Any], seed: TransferRaceSeed) -> None:
    async with sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id == seed.workspace_id))
        await session.execute(delete(User).where(User.id.in_(seed.user_ids)))
        await session.commit()
