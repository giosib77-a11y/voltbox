"""Administrator account management from the command line.

What it does: creates the first administrator and promotes or demotes existing
users. Nobody can become an admin through the public API - RegisterRequest has
no `role` field and ApiRequest forbids extras - so this script is the only way
in, which is exactly the point.
Where it fits: run from backend/ against whatever DATABASE_URL points at.
Notes: the password is never a command-line argument. Arguments land in shell
history, in `ps` output and in CI logs; getpass or an environment variable do not.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from getpass import getpass
from pathlib import Path

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import (
    MIN_ADMIN_PASSWORD_LENGTH,
    hash_password,
    is_common_password,
    is_patterned_password,
)
from app.db.models import ROLE_ADMIN, ROLE_CUSTOMER, User
from app.db.session import SessionLocal, engine
from app.services import auth as auth_service

# S105 is suppressed below because this is the *name* of an environment
# variable, not a password value.
PASSWORD_ENV = "VOLTBOX_ADMIN_PASSWORD"  # noqa: S105


def _read_password() -> str:
    """Password from the environment, or an interactive double prompt."""
    from_env = os.environ.get(PASSWORD_ENV)
    if from_env:
        password = from_env
    else:
        password = getpass("Password: ")
        if password != getpass("Repeat password: "):
            raise SystemExit("პაროლები არ ემთხვევა.")

    # Only an administrator's password is read here, so the administrator's
    # minimum is the one that applies; the rest of the rule is the API's.
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"ადმინისტრატორის პაროლი უნდა იყოს მინიმუმ {MIN_ADMIN_PASSWORD_LENGTH} სიმბოლო."
        )
    if is_common_password(password):
        raise SystemExit("პაროლი ძალიან გავრცელებულია — აირჩიე სხვა.")
    if is_patterned_password(password):
        raise SystemExit("პაროლი განმეორებაა ან მარტივი მიმდევრობა — აირჩიე სხვა.")
    return password


_EMAIL = TypeAdapter(EmailStr)


def _checked_email(email: str) -> str:
    """The email as /auth/login will see it, or SystemExit if login would refuse it.

    The login schema types the field `EmailStr` and ApiRequest strips whitespace
    first; the same two steps here, so the script cannot create an account whose
    address /auth/login answers with 400 (the `.test` domain, for one).
    """
    try:
        return str(_EMAIL.validate_python(email.strip()))
    except ValidationError:
        raise SystemExit(f"{email} არავალიდური ელფოსტაა — /auth/login მას არ მიიღებს.") from None


async def _find(db: AsyncSession, email: str) -> User | None:
    # Assigned first: returned directly, mypy types this call as Any; assigned,
    # as User | None. Measured - the value is the same either way.
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    return user


async def create_admin(email: str, first_name: str, last_name: str) -> None:
    # Before the password prompt and before the database: a bad address should
    # not cost the operator a password first.
    email = _checked_email(email)
    password = _read_password()
    async with SessionLocal() as db:
        if await _find(db, email) is not None:
            raise SystemExit(f"{email} უკვე რეგისტრირებულია — გამოიყენე promote-user.")
        db.add(
            User(
                email=email.strip().lower(),
                password_hash=hash_password(password),
                first_name=first_name,
                last_name=last_name,
                role=ROLE_ADMIN,
                is_active=True,
            )
        )
        await db.commit()
    print(f"✔ ადმინისტრატორი შეიქმნა: {email}")


async def promote_user(email: str) -> None:
    email = _checked_email(email)
    async with SessionLocal() as db:
        user = await _find(db, email)
        if user is None:
            raise SystemExit(f"{email} ვერ მოიძებნა.")
        if user.role == ROLE_ADMIN:
            print(f"= {email} უკვე ადმინისტრატორია.")
            return
        user.role = ROLE_ADMIN
        await db.commit()
    print(f"✔ {email} ახლა ადმინისტრატორია.")
    # No password is set here, so the account keeps the one it has: the rule
    # applies when a new one is set, and sign-in never checks it.
    print(
        f"  პაროლი უცვლელია. ადმინისტრატორის ახალი პაროლი მინიმუმ {MIN_ADMIN_PASSWORD_LENGTH} "
        "სიმბოლოა; ძველი პაროლი ამ წესს არ ექვემდებარება, სანამ არ შეიცვლება."
    )


async def demote_user(email: str) -> None:
    # Deliberately no _checked_email: taking the role away must work on any
    # existing row, including an admin created before that check existed with an
    # address /auth/login refuses. An address that matches no row still exits
    # with "not found" below.
    async with SessionLocal() as db:
        user = await _find(db, email)
        if user is None:
            raise SystemExit(f"{email} ვერ მოიძებნა.")
        user.role = ROLE_CUSTOMER
        # Existing sessions must die with the role. require_admin re-reads the
        # row on every request, so the access token is already useless, but a
        # live refresh token would keep minting new ones for up to 30 days.
        await auth_service.revoke_all(db, user.id)
        await db.commit()
    print(f"✔ {email} აღარ არის ადმინისტრატორი; ყველა სესია გაუქმდა.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage_admin.py",
        description="VoltBox administrator accounts",
        epilog=f"პაროლი იკითხება ინტერაქტიულად ან {PASSWORD_ENV}-იდან, არასოდეს არგუმენტიდან.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin", help="create a new administrator")
    create.add_argument("--email", required=True)
    create.add_argument("--first-name", default="Admin")
    create.add_argument("--last-name", default="")

    promote = sub.add_parser("promote-user", help="give an existing user the admin role")
    promote.add_argument("--email", required=True)

    demote = sub.add_parser("demote-user", help="remove the admin role and revoke sessions")
    demote.add_argument("--email", required=True)

    return parser


async def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "create-admin":
            await create_admin(args.email, args.first_name, args.last_name)
        elif args.command == "promote-user":
            await promote_user(args.email)
        elif args.command == "demote-user":
            await demote_user(args.email)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
