"""ავტორიზაციის ბიზნეს-ლოგიკა.

refresh-ტოკენები rotation-on-use პრინციპით მუშაობს: ყოველი გამოყენებისას ძველი
უქმდება და ახალი გაიცემა. ეს ტოკენის მოპარვას ამჩნევს — თუ მოპარული ტოკენი
უკვე გამოყენებულია, მეორედ აღარ იმუშავებს.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil

from sqlalchemy import ColumnElement, String, case, delete, func, literal, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ConflictError, UnauthorizedError, ValidationError
from app.core.security import (
    PASSWORD_RESET_TTL,
    create_access_token,
    generate_password_reset_token,
    generate_refresh_token,
    hash_password_async,
    hash_password_reset_token,
    hash_refresh_token,
    verify_password_async,
)
from app.db.models import PasswordResetToken, RefreshToken, User

# წარუმატებელი შესვლისას ყოველთვის ერთი და იგივე ტექსტი: არსებული და
# არარსებული ელ. ფოსტის გარჩევა მომხმარებელთა ბაზის აღრიცხვის საშუალებას მისცემდა
INVALID_CREDENTIALS = "Invalid email or password"

# დროის მუდმივობისთვის: არარსებულ მომხმარებელზეც ვასრულებთ ჰეშის შემოწმებას,
# რომ პასუხის დრო არსებობას არ ამხელდეს
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHR2YWx1ZQ$0000000000000000000000000000000000000000000"
)


#: How long after a rotation a replay of the old token is read as a retry
#: rather than as theft.
#:
#: A refresh whose response never reaches the browser leaves it holding the
#: token it already spent - the Set-Cookie was in the reply that was lost - and
#: its next attempt looks exactly like an attacker replaying a stolen token.
#: Treating that as theft would sign people out over a dropped packet. Ten
#: seconds is far longer than the round trip and far shorter than any useful
#: window for someone who has actually stolen the value.
REUSE_GRACE = timedelta(seconds=10)


async def _issue_session(
    db: AsyncSession, user: User, *, family_id: uuid.UUID | None = None
) -> dict[str, object]:
    """A new access/refresh pair. `family_id=None` starts a new login."""
    access_token, expires_at = create_access_token(user.id, user.token_version)
    raw_refresh, refresh_hash, refresh_expires = generate_refresh_token()

    token = RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=refresh_expires)
    # A token rotated out of an existing session stays in that session's family;
    # a fresh login opens one. The row's own id is the family's name, which
    # needs no separate sequence and cannot collide.
    token.family_id = family_id or uuid.uuid4()
    db.add(token)
    await db.flush()

    return {
        "user": user,
        "token": access_token,
        "refresh_token": raw_refresh,
        "expires_at": expires_at,
    }


async def register(
    db: AsyncSession, *, first_name: str, last_name: str, email: str, password: str
) -> dict[str, object]:
    # Hashed before the database is touched, so no connection is held while
    # the hash waits its turn and runs - see `login`.
    password_hash = await hash_password_async(password)
    normalized = email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        raise ConflictError("Email is already registered", code="EMAIL_ALREADY_EXISTS")

    user = User(
        email=normalized,
        password_hash=password_hash,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )
    db.add(user)
    await db.flush()
    return await _issue_session(db, user)


def _too_many_attempts(locked_until: datetime | None) -> UnauthorizedError:
    """The refusal of a locked account. Seconds rounded up so it never reads as "0 left"."""
    remaining = 0.0 if locked_until is None else (locked_until - datetime.now(UTC)).total_seconds()
    return UnauthorizedError(
        "Too many failed sign-in attempts",
        code="TOO_MANY_LOGIN_ATTEMPTS",
        details={"retryAfterSeconds": max(0, ceil(remaining))},
    )


def _unlocked(now: datetime) -> ColumnElement[bool]:
    """No lock on the row, judged on the row as the statement finds it."""
    return or_(User.locked_until.is_(None), User.locked_until <= now)


async def _refused_meanwhile(db: AsyncSession, user: User) -> UnauthorizedError:
    """The refusal for an attempt the row changed under while it was hashing.

    Locked by another attempt: refused as locked, whatever this one guessed.
    Otherwise the password it was checked against has been replaced, so it is
    a wrong password now.
    """
    locked_until = await db.scalar(select(User.locked_until).where(User.id == user.id))
    if locked_until is not None and locked_until > datetime.now(UTC):
        return _too_many_attempts(locked_until)
    return UnauthorizedError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")


async def _record_failure(db: AsyncSession, user: User) -> bool:
    """Count a wrong password, and lock the account once there are too many.

    The count is on the account, not on the caller's address: the limiter in
    front of this endpoint is per IP, and a thousand rented proxies is a
    thousand times the allowance against one email. Every attempt against an
    account has the account in common, and nothing else.

    The database does the arithmetic. Adding one in Python to the count `login`
    had read let every guess of a parallel burst - the thousand proxies above -
    read the same count and write the same count plus one, so the burst moved
    it by one and the lock never came. `failed_login_count + 1` is evaluated on
    the row as the UPDATE finds it: a second guess waits on the first one's row
    lock and adds its one to what that one committed. Both CASEs read the row
    from before this statement, so the guess that reaches the threshold is the
    one that sets the lock, and the count restarts from zero in the same write.

    No row lock is held across the hash. Taking one at the read would queue
    every attempt on the account behind the one before it, each holding a
    pooled connection for an Argon2 run, and a burst against one email would
    take the pool - and the shop - with it.

    False, with nothing counted, when the account was locked after `login` read
    it: one at a time, this guess would have been refused before the hash.
    """
    now = datetime.now(UTC)
    counted = User.failed_login_count + 1
    reached = counted >= settings.max_failed_logins
    lock_until = literal(
        now + timedelta(minutes=settings.login_lock_minutes), User.locked_until.type
    )
    recorded = await db.execute(
        update(User)
        .where(User.id == user.id, _unlocked(now))
        .values(
            failed_login_count=case((reached, 0), else_=counted),
            locked_until=case((reached, lock_until), else_=User.locked_until),
        )
        .returning(User.id)
        .execution_options(synchronize_session="fetch")
    )
    return recorded.first() is not None


async def _clear_failures(db: AsyncSession, user: User) -> bool:
    """Wipe the slate after the right password - unless the row has moved on since.

    Getting in is the proof the attempts before it were the same person
    forgetting. But the lock was checked on the row as `login` read it, before
    the hash, and a guess can have reached the threshold since: a plain write
    of zero from that read erased the lock and the count it had just reached.
    So the write is conditional on the row as it is now, and False when locked.

    Refused, not honoured, because the answer must not depend on the password.
    Every other attempt that lands after the lock is refused whatever it
    guessed; were the right one let in, or even told something different, a
    burst would learn which of its guesses was right despite the lock.

    Nor if the password has changed since `login` read it. A reset or a
    password change ends every session with `revoke_all`, and a sign-in with
    the old password checked in the same instant used to write its refresh
    token after that had run: it kept a session the change was made to end.
    Both write this row before revoking - `reset_password`'s UPDATE, the flush
    in `change_password` - so its row lock orders them against this UPDATE.
    If this one comes first, its token is committed before `revoke_all` can
    look and is revoked with the rest. If the change comes first, this waits
    for it, finds another hash, and the sign-in is refused as a wrong password.

    It writes on every sign-in, clean or not: an UPDATE that matched nothing
    could not say whether the row was clean or locked.
    """
    now = datetime.now(UTC)
    cleared = await db.execute(
        update(User)
        .where(
            User.id == user.id,
            _unlocked(now),
            User.password_hash == user.password_hash,
        )
        .values(failed_login_count=0, locked_until=None)
        .returning(User.id)
        .execution_options(synchronize_session="fetch")
    )
    return cleared.first() is not None


async def login(db: AsyncSession, *, email: str, password: str) -> dict[str, object]:
    user = await db.scalar(select(User).where(User.email == email.strip().lower()))
    # The hash runs in a thread, one at a time per worker, so under a burst it
    # waits its turn as well as taking its ~120 ms. Holding the read's
    # transaction meanwhile would hold its pooled connection, and a burst of
    # sign-ins would empty the pool: the stall the thread exists to remove,
    # moved from the event loop to the database. Nothing is written yet, and
    # everything after the hash is decided on the row as it is then anyway.
    await db.commit()

    if user is None:
        await verify_password_async(password, _DUMMY_HASH)  # დროის გათანაბრება
        raise UnauthorizedError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")

    # Before the hash, deliberately. Argon2 is expensive on purpose, and that
    # cost belongs to people signing in rather than to whoever is guessing.
    # It is not the check that decides - a parallel burst passes it together,
    # on the row as it was read - but it spares the hash once a lock is in.
    #
    # This answer does say the account exists, which the generic one above
    # avoids. Registration already answers that question - EMAIL_ALREADY_EXISTS
    # - so hiding it here buys nothing, and a shopper locked out deserves to be
    # told why rather than being left to retype a password that is correct.
    if user.locked_until is not None and user.locked_until > datetime.now(UTC):
        raise _too_many_attempts(user.locked_until)

    # The check that decides is in the statement that records the outcome.
    if not await verify_password_async(password, user.password_hash):
        if not await _record_failure(db, user):
            raise await _refused_meanwhile(db, user)
        raise UnauthorizedError(INVALID_CREDENTIALS, code="INVALID_CREDENTIALS")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled", code="ACCOUNT_DISABLED")
    if not await _clear_failures(db, user):
        raise await _refused_meanwhile(db, user)

    return await _issue_session(db, user)


def invalid_refresh_token() -> UnauthorizedError:
    """One sentence for every way a refresh can fail.

    Missing cookie, expired token, already-spent token: telling them apart
    would tell a caller which of those it is holding.
    """
    return UnauthorizedError("Refresh token is invalid or expired", code="INVALID_REFRESH_TOKEN")


async def _handle_possible_reuse(db: AsyncSession, token_hash: str) -> None:
    """A spent token came back. Decide whether that means theft, and act.

    Rotation is what makes theft visible: once a token has been exchanged it can
    never legitimately be presented again, so a second appearance means two
    copies of it exist. Noticing that and doing nothing - which is what happened
    before - leaves the thief holding a session that keeps renewing itself.

    The whole family goes, not the whole account: the person's other devices
    were never in danger and signing them out would punish the victim. And a
    replay inside REUSE_GRACE is left alone, because a refresh whose response
    was lost produces exactly this shape and is not an attack.

    Never raises. The caller's answer is the same 401 either way, and the reason
    for it is not the client's business.
    """
    spent = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if spent is None or spent.revoked_at is None:
        # Unknown or merely expired: nothing to conclude from it.
        return

    if datetime.now(UTC) - spent.revoked_at <= REUSE_GRACE:
        return

    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.family_id == spent.family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=func.now())
        .execution_options(synchronize_session=False)
    )


async def refresh(db: AsyncSession, *, raw_token: str) -> dict[str, object]:
    """Exchange a refresh token for a new session, exactly once.

    The revocation is the check. Reading the row, deciding it was usable and
    then revoking it in a second statement left a window in which two requests
    carrying the same token both read `revoked_at IS NULL` and both received a
    session - which is precisely what rotation-on-use exists to prevent, and it
    happens on its own whenever a client fires parallel requests after an
    access token expires.

    One conditional UPDATE closes it: the second caller's statement waits on
    the row, re-evaluates the WHERE clause once the first commits, matches
    nothing, and gets a 401.

    The account's row is locked first, before the token's. A reset, a password
    change and a block all end every session with `revoke_all`, and a rotation
    in the same instant used to write its new token after that had looked: it
    claimed the old token, `revoke_all` waited on that row and then skipped
    it as already revoked, and the new token, inserted after `revoke_all`'s
    statement began, was never seen - a live session the change was made to
    end. All three write this row before revoking, so the lock orders them
    against the rotation. If the rotation comes first, its new token is
    committed before `revoke_all` looks, and is revoked with the rest; if the
    change comes first, the rotation waits for it and finds its token revoked.
    Account row, then tokens, in that order everywhere: the other order beside
    this one could deadlock, which is why `revoke_all` bumps the version first.
    """
    token_hash = hash_refresh_token(raw_token)

    owner = await db.scalar(
        select(RefreshToken.user_id).where(RefreshToken.token_hash == token_hash)
    )
    user = (
        None
        if owner is None
        else await db.scalar(
            select(User)
            .where(User.id == owner)
            # FOR NO KEY UPDATE: excludes the writers above without blocking
            # the inserts elsewhere that only reference the row.
            .with_for_update(key_share=True)
            # A fresh row, not one this session may already hold.
            .execution_options(populate_existing=True)
        )
    )

    claimed = (
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > func.now(),
            )
            .values(revoked_at=func.now())
            .returning(RefreshToken.user_id, RefreshToken.family_id)
            # Nothing in this session holds the row, so there is nothing to
            # synchronise and the extra SELECT it would cost is pointless.
            .execution_options(synchronize_session=False)
        )
    ).one_or_none()

    if claimed is None:
        await _handle_possible_reuse(db, token_hash)
        raise invalid_refresh_token()

    if user is None or not user.is_active:
        # The revocation rolls back with the transaction, so a suspended
        # account that is re-enabled keeps the sessions it had.
        raise UnauthorizedError("Account is not available", code="ACCOUNT_DISABLED")

    return await _issue_session(db, user, family_id=claimed.family_id)


async def logout(db: AsyncSession, *, raw_token: str | None) -> None:
    """გასვლა refresh-ტოკენს ბაზაში აუქმებს.

    კლიენტის მხარეს ტოკენის წაშლა საკმარისი არაა — მოპარული refresh-ტოკენი
    სერვერზე მაინც მოქმედი დარჩებოდა.
    """
    if not raw_token:
        return
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all(db: AsyncSession, user_id: object) -> None:
    """პაროლის შეცვლისას ყველა სესია უნდა გაითიშოს.

    Both halves of a session, not just the half that can be deleted. Revoking
    the refresh tokens stops a session being *extended*; the access tokens
    already handed out keep working until they expire, which was up to another
    thirty minutes of the thief still being signed in after the owner changed a
    stolen password. Moving `tokens_valid_from` refuses those too.

    A password reset link already sent goes as well. It is a way in that does
    not need the password, so a change of password - or a blocked account -
    that left it working would leave whoever holds that email able to undo it.

    The account's row is written first, before any token: `refresh` and
    `login` take that row before writing a token, and the lock is what keeps
    them from slipping a new one in after the revocation has looked. Tokens
    first would also take the two locks in the opposite order to `refresh`,
    and the two could deadlock.
    """
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(token_version=User.token_version + 1)
        # The row is usually already loaded in this session - `change_password`
        # is holding it - and the sessions here are created with
        # `expire_on_commit=False`, so without this the instance would keep the
        # old value and a read on the same session would be answered from it.
        .execution_options(synchronize_session="fetch")
    )
    now = datetime.now(UTC)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.execute(
        delete(PasswordResetToken)
        .where(PasswordResetToken.user_id == user_id)
        .execution_options(synchronize_session=False)
    )


async def change_password(
    db: AsyncSession, *, user: User, current_password: str, new_password: str
) -> None:
    # Ends the transaction that loaded `user`, so its connection is not held
    # through two hashes - see `login`.
    await db.commit()
    if not await verify_password_async(current_password, user.password_hash):
        raise ValidationError(
            "Current password is incorrect",
            code="INVALID_CURRENT_PASSWORD",
            details=[{"field": "currentPassword", "message": "Current password is incorrect"}],
        )
    user.password_hash = await hash_password_async(new_password)
    await db.flush()
    await revoke_all(db, user.id)


@dataclass(frozen=True)
class IssuedReset:
    """A reset token that now exists, for the email that carries it."""

    user_id: uuid.UUID
    token: str


async def issue_password_reset(db: AsyncSession, *, email: str) -> IssuedReset | None:
    """A reset token for the active account at `email`, or None when there is none.

    One statement whatever the answer, and that is the point. The INSERT takes
    its row from a SELECT on `users`, so an address with no account runs the
    same statement and inserts nothing. A lookup followed by a write only when
    it found someone - the obvious shape - would make a registered address the
    slower answer, and the timing would say who has an account even though the
    response does not. It is what `login` does with a dummy Argon2 hash, done
    here with the query instead: the token is generated either way, the same
    statement runs either way, and the caller commits either way.

    The upsert on the account replaces an earlier link, so only the newest
    email's works. A blocked account gets none: it could not sign in with the
    new password anyway.
    """
    raw, token_hash = generate_password_reset_token()
    candidates = select(
        User.id,
        literal(token_hash, String),
        # The database's clock, the one `reset_password` compares against.
        func.now() + PASSWORD_RESET_TTL,
    ).where(User.email == email.strip().lower(), User.is_active.is_(True))
    insert = pg_insert(PasswordResetToken).from_select(
        ["user_id", "token_hash", "expires_at"], candidates
    )
    upsert = insert.on_conflict_do_update(
        index_elements=[PasswordResetToken.user_id],
        set_={
            "token_hash": insert.excluded.token_hash,
            "expires_at": insert.excluded.expires_at,
            "created_at": func.now(),
        },
    ).returning(PasswordResetToken.user_id)

    user_id = (await db.execute(upsert)).scalar_one_or_none()
    return None if user_id is None else IssuedReset(user_id=user_id, token=raw)


def invalid_reset_token() -> ValidationError:
    """One answer for a link that is unknown, used, expired or replaced."""
    return ValidationError(
        "The password reset link is invalid or has expired", code="INVALID_RESET_TOKEN"
    )


async def reset_password(db: AsyncSession, *, raw_token: str, new_password: str) -> None:
    """Set a new password through a reset link, exactly once, and end every session.

    The DELETE is the check, as the UPDATE is in `refresh`: of two submissions
    of one link, the second waits on the row, finds it gone once the first
    commits, and is refused. Nothing reads the row first and decides later.

    A failure after the claim - the account blocked in the meantime - raises,
    and the rollback puts the row back; the link is refused either way.

    The new password is hashed first, before any statement, so no connection
    is held while the hash waits its turn and runs - see `login`. A link that
    turns out to be invalid has then cost a hash, as a wrong password does.
    """
    password_hash = await hash_password_async(new_password)
    claimed = (
        await db.execute(
            delete(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == hash_password_reset_token(raw_token),
                PasswordResetToken.expires_at > func.now(),
            )
            .returning(PasswordResetToken.user_id)
            .execution_options(synchronize_session=False)
        )
    ).scalar_one_or_none()
    if claimed is None:
        raise invalid_reset_token()

    user = await db.scalar(select(User).where(User.id == claimed))
    if user is None or not user.is_active:
        raise invalid_reset_token()

    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            password_hash=password_hash,
            # Whoever opened the link proved they hold the mailbox, which
            # outranks the failed guesses that locked the account; left in
            # place, the lock would refuse the new password for up to
            # login_lock_minutes.
            #
            # A statement, not attributes on `user`: the ORM leaves out a
            # column it believes unchanged, and `user` was read before this
            # write. A guess that locked the account in between kept its lock
            # through the reset, because `locked_until` was None when read.
            failed_login_count=0,
            locked_until=None,
        )
        .execution_options(synchronize_session="fetch")
    )
    await revoke_all(db, user.id)


async def update_profile(db: AsyncSession, *, user: User, changes: dict[str, object]) -> User:
    if (email := changes.get("email")) is not None:
        normalized = str(email).strip().lower()
        if normalized != user.email:
            taken = await db.scalar(
                select(User).where(User.email == normalized, User.id != user.id)
            )
            if taken is not None:
                raise ConflictError("Email is already registered", code="EMAIL_ALREADY_EXISTS")
        user.email = normalized

    for field in ("first_name", "last_name", "phone"):
        if (value := changes.get(field)) is not None:
            setattr(user, field, str(value).strip())

    await db.flush()
    return user
