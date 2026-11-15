"""scripts/manage_admin.py: an address /auth/login would refuse never reaches the database.

What it covers: `create-admin audit-admin@example.test` used to succeed and leave
an administrator who could never sign in - the login schema's `EmailStr` rejects
the `.test` domain with 400. create-admin and promote-user now apply that same
check first, and exit before the password prompt and before any row is written.
demote-user does not: removing the role must work on any existing row, including
an admin created with such an address before the check. The check is compared
against LoginRequest itself, so the two cannot drift apart unnoticed.
Notes: the script opens its own sessions; they are pointed at the test
transaction (a savepoint per commit), so nothing outlives the test.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from app.core.security import hash_refresh_token
from app.db.models import ROLE_ADMIN, ROLE_CUSTOMER, RefreshToken, User
from app.schemas.auth import LoginRequest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories import load_script, make_user

SCRIPT = load_script("manage_admin")

INVALID = ["audit-admin@example.test", "not-an-email", "", "a@b", "two@@example.com"]


@pytest.fixture(autouse=True)
def _script_uses_the_test_transaction(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    assert db.bind is not None
    monkeypatch.setattr(
        SCRIPT,
        "SessionLocal",
        async_sessionmaker(
            bind=db.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ),
    )


@pytest.fixture
def no_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading a password at all fails the test: the email is checked first."""
    monkeypatch.delenv(SCRIPT.PASSWORD_ENV, raising=False)

    def _prompted(*_: Any) -> str:
        raise AssertionError("the password was read before the email was checked")

    monkeypatch.setattr(SCRIPT, "getpass", _prompted)


async def _users(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


@pytest.mark.parametrize("email", INVALID)
async def test_create_admin_refuses_an_email_login_would_refuse(
    db: AsyncSession, no_prompt: None, email: str
) -> None:
    with pytest.raises(SystemExit, match="არავალიდური ელფოსტაა"):
        await SCRIPT.create_admin(email, "Admin", "")

    assert await _users(db) == 0


@pytest.mark.parametrize("email", INVALID)
async def test_promote_user_refuses_an_invalid_email(db: AsyncSession, email: str) -> None:
    with pytest.raises(SystemExit, match="არავალიდური ელფოსტაა"):
        await SCRIPT.promote_user(email)

    assert await _users(db) == 0


async def test_demote_user_works_on_an_admin_whose_stored_email_login_refuses(
    db: AsyncSession,
) -> None:
    """Removing the role must work on any existing row, e.g. one made before A-044."""
    admin = await make_user(db, email="audit-admin@example.test", role=ROLE_ADMIN)
    token = RefreshToken(
        user_id=admin.id,
        token_hash=hash_refresh_token("demote-test-token"),
        family_id=uuid.uuid4(),
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db.add(token)
    await db.flush()
    version = admin.token_version

    await SCRIPT.demote_user("audit-admin@example.test")

    await db.refresh(admin)
    await db.refresh(token)
    assert admin.role == ROLE_CUSTOMER
    assert admin.token_version == version + 1
    assert token.revoked_at is not None


async def test_demote_user_with_no_such_row_still_says_not_found(db: AsyncSession) -> None:
    with pytest.raises(SystemExit, match="ვერ მოიძებნა"):
        await SCRIPT.demote_user("not-an-email")


async def test_a_valid_email_creates_an_admin(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SCRIPT.PASSWORD_ENV, "a-long-unusual-passphrase-4821")

    await SCRIPT.create_admin("  New.Admin@Example.com ", "Nino", "K")

    created = await db.scalar(select(User).where(User.email == "new.admin@example.com"))
    assert created is not None
    assert created.role == ROLE_ADMIN
    assert created.is_active


async def test_valid_emails_still_promote_and_demote(db: AsyncSession) -> None:
    user = await make_user(db, email="staff@example.com")

    await SCRIPT.promote_user(" Staff@Example.com ")
    await db.refresh(user)
    assert user.role == ROLE_ADMIN

    await SCRIPT.demote_user("staff@example.com")
    await db.refresh(user)
    assert user.role == ROLE_CUSTOMER


@pytest.mark.parametrize(
    "email", [*INVALID, "ok@example.com", "  ok@example.com  ", "Ok@Example.GE"]
)
def test_the_check_agrees_with_the_login_schema(email: str) -> None:
    try:
        LoginRequest.model_validate({"email": email, "password": "x"})
        login_accepts = True
    except ValidationError:
        login_accepts = False

    try:
        SCRIPT._checked_email(email)
        script_accepts = True
    except SystemExit:
        script_accepts = False

    assert script_accepts == login_accepts
