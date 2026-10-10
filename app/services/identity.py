"""Identity service.

Recovery design: argon2 hashes are salted, so a passphrase alone cannot be looked up.
`recover(anon_id, passphrase)` locates the account by its anon_id (high-entropy handle
shown to the user at bootstrap, which they store with their passphrase) and then
verifies the passphrase against recovery_hash. All failures raise the same
InvalidCredentials, and a dummy verify runs when no account matches (timing parity).
"""
import secrets
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token, hash_secret, verify_secret
from app.models import User
from app.models.user import UserRole
from app.repositories.users import UserRepository

ADMIN_ROLES = {UserRole.admin, UserRole.reviewer}
_DUMMY_HASH = hash_secret("ubuzima-dummy-secret")


class InvalidCredentials(Exception):
    pass


@dataclass
class Tokens:
    access_token: str
    refresh_token: str


def issue_tokens(user: User) -> Tokens:
    sub = str(user.id)
    return Tokens(create_access_token(sub, user.role.value), create_refresh_token(sub))


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)

    async def bootstrap_anon(self) -> tuple[User, Tokens]:
        user = await self.users.create(anon_id=secrets.token_urlsafe(24), role=UserRole.user)
        return user, issue_tokens(user)

    async def upgrade(self, user: User, passphrase: str) -> User:
        if user.role != UserRole.user:
            raise InvalidCredentials("only end-user accounts can set a recovery passphrase")
        return await self.users.update(
            user, recovery_hash=hash_secret(passphrase), is_upgraded=True)

    async def recover(self, anon_id: str, passphrase: str) -> tuple[User, Tokens]:
        user = await self.users.get_by_anon_id(anon_id)
        hashed = user.recovery_hash if user and user.recovery_hash else _DUMMY_HASH
        ok = verify_secret(passphrase, hashed)
        if not (ok and user and user.is_upgraded and not user.disabled
                and user.role == UserRole.user):
            raise InvalidCredentials("invalid credentials")
        return user, issue_tokens(user)

    async def refresh(self, user: User) -> Tokens:
        if user.disabled:
            raise InvalidCredentials("account disabled")
        return issue_tokens(user)

    async def login_admin(self, email: str, password: str) -> Tokens:
        user = await self.users.get_by_email(email)
        hashed = user.password_hash if user and user.password_hash else _DUMMY_HASH
        ok = verify_secret(password, hashed)
        if not (ok and user and user.role in ADMIN_ROLES and not user.disabled):
            raise InvalidCredentials("invalid credentials")
        return issue_tokens(user)
