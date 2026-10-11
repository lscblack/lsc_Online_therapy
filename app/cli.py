"""Management CLI.  Usage: python -m app.cli create_admin --email you@org [--password ...]"""
import argparse
import asyncio
import getpass
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine, get_sessionmaker
from app.core.security import ahash_secret
from app.models.user import UserRole
from app.repositories.users import UserRepository

MIN_PASSWORD = 12


class AdminExists(Exception):
    pass


async def create_admin(session: AsyncSession, email: str, password: str,
                       role: UserRole = UserRole.admin):
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("a valid email is required")
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
    repo = UserRepository(session)
    if await repo.get_by_email(email):
        raise AdminExists(f"user {email} already exists")
    import secrets
    user = await repo.create(anon_id=f"admin-{secrets.token_urlsafe(16)}", email=email,
                             password_hash=await ahash_secret(password), role=role)
    await session.commit()
    return user


async def _run(email: str, password: str, role: UserRole) -> int:
    try:
        async with get_sessionmaker()() as s:
            u = await create_admin(s, email, password, role)
        print(f"Created {u.role.value} {u.email} (id {u.id})")
        return 0
    except (AdminExists, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        await get_engine().dispose()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create_admin", help="create the first admin (or reviewer) account")
    c.add_argument("--email", required=True)
    c.add_argument("--password", help="omit to be prompted (preferred; avoids shell history)")
    c.add_argument("--role", choices=["admin", "reviewer"], default="admin")
    a = p.parse_args(argv)
    password = a.password or getpass.getpass("Password: ")
    return asyncio.run(_run(a.email, password, UserRole(a.role)))


if __name__ == "__main__":
    raise SystemExit(main())
