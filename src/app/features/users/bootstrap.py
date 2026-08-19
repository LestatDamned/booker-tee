import asyncio
import sys
from getpass import getpass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password
from app.core.settings import Settings
from app.db import model_registry as model_registry  # noqa: F401
from app.db.base import utc_now
from app.db.session import session_factory
from app.features.users.errors import BootstrapOwnerError, UserError
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.features.users.service import clean_user_name, normalize_email, validate_password
from app.features.workspaces.models import WorkspaceAuditEventType
from app.features.workspaces.repository import WorkspaceRepository


class OwnerBootstrapService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.workspaces = WorkspaceRepository(session)

    async def create_first_owner(self, *, email: str, name: str, password: str) -> User:
        normalized_email = normalize_email(email)
        cleaned_name = clean_user_name(name)
        if cleaned_name is None:
            raise BootstrapOwnerError("Owner name is required.")
        password_hash = hash_password(
            validate_password(password, minimum_length=self.settings.password_min_length)
        )

        try:
            await self.users.lock_for_owner_bootstrap()
            if await self.users.has_any():
                raise BootstrapOwnerError("Owner bootstrap has already been completed.")

            user = await self.users.create(
                email=normalized_email,
                password_hash=password_hash,
                name=cleaned_name,
            )
            user.email_verified_at = utc_now()
            (
                workspace,
                _membership,
            ) = await self.workspaces.create_personal_workspace_with_owner_membership(user.id)
            await self.workspaces.create_audit_event(
                workspace_id=workspace.id,
                event_type=WorkspaceAuditEventType.WORKSPACE_CREATED,
                actor_user_id=user.id,
                entity_type="workspace",
                entity_id=workspace.id,
                details={
                    "name": workspace.name,
                    "type": workspace.type.value,
                    "default_currency": workspace.default_currency,
                },
            )
            await self.session.commit()
            return user
        except Exception:
            await self.session.rollback()
            raise


async def run_owner_bootstrap(*, email: str, name: str, password: str) -> None:
    settings = get_settings()
    settings.validate_for_runtime()
    async with session_factory() as session:
        await OwnerBootstrapService(session, settings).create_first_owner(
            email=email,
            name=name,
            password=password,
        )


def main() -> None:
    try:
        if not sys.stdin.isatty():
            raise BootstrapOwnerError("Owner bootstrap requires an interactive terminal.")
        email = input("Owner email: ")
        name = input("Owner name: ")
        password = getpass("Owner password: ")
        if password != getpass("Repeat password: "):
            raise BootstrapOwnerError("Passwords do not match.")
        asyncio.run(run_owner_bootstrap(email=email, name=name, password=password))
    except (EOFError, KeyboardInterrupt):
        print("\nOwner bootstrap cancelled.", file=sys.stderr)
        raise SystemExit(1) from None
    except (UserError, RuntimeError) as error:
        print(f"Owner bootstrap failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
    print("Owner bootstrap completed.")


if __name__ == "__main__":
    main()
