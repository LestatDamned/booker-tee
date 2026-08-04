from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.users.errors import (
    CurrentSessionCannotBeRevokedError,
    UserSessionNotFoundError,
)
from app.features.users.repository import UserRepository


@dataclass(frozen=True)
class UserSessionSnapshot:
    id: UUID
    is_current: bool
    device_summary: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime


class UserSessionService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)

    async def list_active(
        self,
        *,
        user_id: UUID,
        current_session_id: UUID,
    ) -> list[UserSessionSnapshot]:
        now = utc_now()
        idle_cutoff = now - timedelta(seconds=self.settings.session_idle_timeout_seconds)
        revoked_count = await self.users.revoke_expired_sessions_for_user(
            user_id=user_id,
            now=now,
            idle_cutoff=idle_cutoff,
        )
        sessions = await self.users.list_active_sessions_for_user(
            user_id=user_id,
            now=now,
            idle_cutoff=idle_cutoff,
        )
        if revoked_count:
            await self.session.commit()
        snapshots = [
            UserSessionSnapshot(
                id=user_session.id,
                is_current=user_session.id == current_session_id,
                device_summary=user_session.user_agent_summary or "Неизвестный браузер",
                created_at=user_session.created_at,
                last_seen_at=user_session.last_seen_at,
                expires_at=user_session.expires_at,
            )
            for user_session in sessions
        ]
        return sorted(snapshots, key=lambda item: not item.is_current)

    async def revoke(
        self,
        *,
        user_id: UUID,
        current_session_id: UUID,
        session_id: UUID,
    ) -> None:
        if session_id == current_session_id:
            raise CurrentSessionCannotBeRevokedError(
                "Текущую сессию можно завершить только через выход."
            )
        revoked = await self.users.revoke_owned_session(
            user_id=user_id,
            session_id=session_id,
            revoked_at=utc_now(),
        )
        if not revoked:
            raise UserSessionNotFoundError("Сессия не найдена.")
        await self.session.commit()

    async def revoke_others(self, *, user_id: UUID, current_session_id: UUID) -> int:
        revoked_count = await self.users.revoke_other_sessions(
            user_id=user_id,
            current_session_id=current_session_id,
        )
        await self.session.commit()
        return revoked_count


def summarize_user_agent(user_agent: str | None) -> str:
    if not user_agent:
        return "Неизвестный браузер"

    browsers = (
        ("Edg/", "Microsoft Edge"),
        ("EdgiOS/", "Microsoft Edge"),
        ("Firefox/", "Firefox"),
        ("FxiOS/", "Firefox"),
        ("Chrome/", "Chrome"),
        ("CriOS/", "Chrome"),
        ("Safari/", "Safari"),
    )
    platforms = (
        ("Android", "Android"),
        ("iPhone", "iPhone"),
        ("iPad", "iPad"),
        ("Windows", "Windows"),
        ("Macintosh", "macOS"),
        ("Linux", "Linux"),
    )
    browser = next((label for marker, label in browsers if marker in user_agent), None)
    platform = next((label for marker, label in platforms if marker in user_agent), None)
    if browser is None:
        return "Неизвестный браузер"
    return f"{browser} · {platform}" if platform else browser
